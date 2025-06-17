import streamlit as st
import asyncio
import pandas as pd
import os
import unicodedata
import re
from dotenv import load_dotenv
from telethon.sync import TelegramClient
from telethon.tl.functions.messages import GetDialogsRequest
from telethon.tl.types import InputPeerEmpty
from telethon.sessions import StringSession

# Load environment variables
load_dotenv()

# Function to normalize text for better Hebrew and Unicode search
def normalize_text(text):
    """Normalize text for better search matching, especially for Hebrew"""
    if not text:
        return ""
    
    # Remove RTL/LTR marks and other invisible characters
    text = re.sub(r'[\u200e\u200f\u202a-\u202e]', '', text)
    
    # Normalize Unicode (NFD decomposition then NFC composition)
    text = unicodedata.normalize('NFD', text)
    text = unicodedata.normalize('NFC', text)
    
    # Remove extra whitespace
    text = ' '.join(text.split())
    
    return text

# Get API credentials from environment variables or Streamlit secrets
try:
    # Try to get from Streamlit secrets first (for deployed apps)
    API_ID = st.secrets["TELEGRAM_API_ID"]
    API_HASH = st.secrets["TELEGRAM_API_HASH"]
    SESSION_STRING = st.secrets.get("TELEGRAM_SESSION_STRING", "")
except (KeyError, FileNotFoundError):
    # Fall back to environment variables (for local development)
    API_ID = os.getenv('TELEGRAM_API_ID')
    API_HASH = os.getenv('TELEGRAM_API_HASH')
    SESSION_STRING = os.getenv('TELEGRAM_SESSION_STRING', "")

# Streamlit UI
st.title("🔍 Telegram Group Keyword Scraper")

# Check if API credentials are loaded
if not API_ID or not API_HASH:
    st.error("⚠️ API credentials not found! Please create a .env file with TELEGRAM_API_ID and TELEGRAM_API_HASH")
    st.stop()

st.success("✅ Ready to scrape! (Session authenticated)")

# Main App Interface
st.subheader("📥 Message Scraper")

group_link = st.text_input("🔗 Enter the Telegram group link (public or invite link)")

# Keywords section with include/exclude
col1, col2 = st.columns(2)
with col1:
    keywords_input = st.text_input("🔍 Include keywords (comma-separated)", 
                                   placeholder="e.g. massage, עיסוי, therapy")
with col2:
    exclude_keywords_input = st.text_input("❌ Exclude keywords (comma-separated)", 
                                           placeholder="e.g. erotic, sexual")

# Advanced options
with st.expander("⚙️ Advanced Options"):
    col1, col2 = st.columns(2)
    with col1:
        message_limit = st.number_input("📊 Maximum messages to scan", 
                                        min_value=100, max_value=5000000000, value=10000, step=500,
                                        help="Limits processing time and prevents rate limiting")
        case_sensitive = st.checkbox("🔤 Case sensitive search")
    with col2:
        allow_duplicates = st.checkbox("🔄 Allow multiple messages from same user", 
                                       value=True,
                                       help="If unchecked, only shows latest message per user")
        download_format = st.selectbox("📁 Download format", ["Excel (.xlsx)", "CSV (.csv)"])

if st.button("🚀 Start Scraping", type="primary"):
    if not all([group_link, keywords_input]):
        st.error("❌ Please fill in the group link and include keywords.")
    else:
        keywords = [k.strip() for k in keywords_input.split(",") if k.strip()]
        exclude_keywords = [k.strip() for k in exclude_keywords_input.split(",") if k.strip()] if exclude_keywords_input else []
        
        # Debug info for Hebrew keywords
        has_hebrew_keywords = any('\u0590' <= char <= '\u05FF' for keyword in keywords for char in keyword)
        if has_hebrew_keywords:
            with st.expander("🔍 Hebrew Search Debug Info"):
                st.write("**Original Keywords:**", keywords)
                normalized_kw = [normalize_text(k) for k in keywords]
                st.write("**Normalized Keywords:**", normalized_kw)
                if not case_sensitive:
                    st.write("**Lowercase Keywords:**", [k.lower() for k in normalized_kw])
                st.info("💡 If search fails, try copying keywords directly from Telegram messages")
        
        # Define async scraping logic
        async def scrape_keywords():
            try:
                # Create client using session from secrets or generate new one
                if SESSION_STRING:
                    # Use existing session string from secrets
                    client = TelegramClient(
                        StringSession(SESSION_STRING), 
                        int(API_ID), 
                        API_HASH,
                        connection_retries=5,
                        retry_delay=1
                    )
                else:
                    # Create new session (for first-time setup)
                    client = TelegramClient(
                        StringSession(), 
                        int(API_ID), 
                        API_HASH,
                        connection_retries=5,
                        retry_delay=1
                    )
                
                with st.spinner("🔌 Connecting to Telegram..."):
                    await client.start()
                st.success("✅ Connected to Telegram!")
                
                # If this is a new session, display the session string for saving
                if not SESSION_STRING:
                    session_string = client.session.save()
                    st.warning("🔐 **First-time setup detected!**")
                    st.info("📋 **Save this session string to your Streamlit secrets:**")
                    st.code(session_string, language="text")
                    st.info("💡 Add `TELEGRAM_SESSION_STRING = \"your_session_string_here\"` to your secrets")
                    st.info("🔄 After adding to secrets, restart the app")
                
                with st.spinner("🔍 Getting group information..."):
                    group = await client.get_entity(group_link)
                st.success(f"✅ Found group: **{group.title}**")
                st.info(f"👥 Group members: {group.participants_count if hasattr(group, 'participants_count') else 'N/A'}")

                # Progress tracking
                st.info("📥 Starting message scan...")
                progress_bar = st.progress(0)
                status_text = st.empty()

                data = []
                user_message_count = {}  # Track messages per user
                user_latest_message = {}  # Track latest message per user
                user_messages = {}  # Store all messages per user
                message_count = 0
                matches_found = 0
                
                # Add Hebrew search info
                has_hebrew = any('\u0590' <= char <= '\u05FF' for keyword in keywords for char in keyword)
                if has_hebrew:
                    st.info("🔤 Hebrew text detected - Using enhanced Unicode search")
                
                try:
                    async for msg in client.iter_messages(group, limit=message_limit):
                        message_count += 1
                        
                        # Update progress every 50 messages
                        if message_count % 50 == 0:
                            progress = min(message_count / message_limit, 1.0)
                            progress_bar.progress(progress)
                            status_text.text(f"📥 Scanned: {message_count:,} messages | Found: {matches_found} matches")
                        
                        # Add periodic delay to prevent rate limiting
                        if message_count % 100 == 0:
                            await asyncio.sleep(0.1)  # Small delay every 100 messages
                        
                        if msg.text and msg.sender:
                            # Normalize message text for better Hebrew search
                            normalized_msg_text = normalize_text(msg.text)
                            
                            # Check for keyword matches with normalization
                            text_to_search = normalized_msg_text if case_sensitive else normalized_msg_text.lower()
                            
                            # Normalize keywords for comparison
                            normalized_keywords = [normalize_text(k) for k in keywords]
                            keywords_to_check = normalized_keywords if case_sensitive else [k.lower() for k in normalized_keywords]
                            
                            normalized_exclude = [normalize_text(k) for k in exclude_keywords] if exclude_keywords else []
                            exclude_to_check = normalized_exclude if case_sensitive else [k.lower() for k in normalized_exclude]
                            
                            # Check if text contains include keywords
                            include_match = any(word in text_to_search for word in keywords_to_check)
                            
                            # Check if text contains exclude keywords
                            exclude_match = any(word in text_to_search for word in exclude_to_check) if exclude_to_check else False
                            
                            if include_match and not exclude_match:
                                matches_found += 1
                                username = msg.sender.username if msg.sender.username else f"ID_{msg.sender.id}"
                                user_id = msg.sender.id
                                
                                # Count messages per user
                                user_message_count[user_id] = user_message_count.get(user_id, 0) + 1
                                
                                # Find which keyword matched (use original keyword for display)
                                matched_keyword = None
                                for orig_kw, norm_kw in zip(keywords, keywords_to_check):
                                    if norm_kw in text_to_search:
                                        matched_keyword = orig_kw
                                        break
                                if not matched_keyword:
                                    matched_keyword = keywords[0]
                                
                                # Create message link
                                msg_link = (
                                    f"https://t.me/c/{str(group.id)[4:]}/{msg.id}"
                                    if str(group.id).startswith("-100")
                                    else f"{group_link}/{msg.id}"
                                )
                                
                                # Get message date
                                msg_date = msg.date.strftime("%Y-%m-%d %H:%M:%S") if msg.date else "N/A"
                                
                                # Clean message text for better CSV compatibility
                                clean_text = msg.text.replace('\n', ' ').replace('\r', ' ')
                                clean_text = ''.join(char for char in clean_text if ord(char) < 65536)  # Remove problematic Unicode
                                preview_text = clean_text[:100] + "..." if len(clean_text) > 100 else clean_text
                                
                                message_data = [
                                    f"@{username}", 
                                    matched_keyword, 
                                    group.title, 
                                    msg_link, 
                                    msg_date,
                                    preview_text,
                                    0  # Placeholder for count - will be updated later
                                ]
                                
                                # Store messages per user
                                if user_id not in user_messages:
                                    user_messages[user_id] = []
                                user_messages[user_id].append(message_data)
                                
                                # Track latest message per user
                                if user_id not in user_latest_message or msg.date > user_latest_message[user_id]['date']:
                                    user_latest_message[user_id] = {
                                        'data': message_data,
                                        'date': msg.date,
                                        'user_id': user_id
                                    }
                
                except Exception as scan_error:
                    st.warning(f"⚠️ Scan stopped at {message_count:,} messages: {str(scan_error)}")
                    st.info("💡 This might be due to:")
                    st.info("• Rate limiting by Telegram")
                    st.info("• Limited access to older messages")
                    st.info("• Group permission restrictions")
                    st.info("• Network connectivity issues")
                
                await client.disconnect()
                progress_bar.progress(1.0)
                status_text.text(f"✅ Scan complete! {message_count:,} messages scanned")
                
                # Prepare final data with correct counts
                if allow_duplicates:
                    # Show all messages with correct counts
                    data = []
                    for user_id, messages in user_messages.items():
                        total_count = user_message_count[user_id]
                        for msg_data in messages:
                            msg_data[6] = total_count  # Update count with total
                            data.append(msg_data)
                    
                    # Remove count column for duplicate mode
                    data = [row[:-1] for row in data]  # Remove last column (count)
                    columns = [
                        "Username", 
                        "Matched Keyword", 
                        "Group Name", 
                        "Message Link", 
                        "Date",
                        "Message Preview"
                    ]
                else:
                    # Show only latest message per user with correct counts
                    data = []
                    for user_id, msg_info in user_latest_message.items():
                        msg_data = msg_info['data'].copy()
                        msg_data[6] = user_message_count[user_id]  # Set correct total count
                        data.append(msg_data)
                    
                    columns = [
                        "Username", 
                        "Matched Keyword", 
                        "Group Name", 
                        "Message Link", 
                        "Date",
                        "Message Preview",
                        "Total Messages"
                    ]
                
                if data:
                    df = pd.DataFrame(data, columns=columns)
                    
                    # Display results
                    st.success(f"🎉 **Scraping Complete!** Found **{len(data)}** matching messages")
                    
                    # Show duplicate handling info
                    if not allow_duplicates:
                        total_unique_users = len(set([row[0] for row in data]))
                        st.info(f"📊 **Duplicate filtering applied**: {len(data)} unique users (latest message only)")
                    
                    # Stats
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("📊 Total Messages", f"{message_count:,}")
                    with col2:
                        st.metric("🎯 Matches Found", len(data))
                    with col3:
                        st.metric("📈 Match Rate", f"{(len(data)/message_count)*100:.2f}%")
                    
                    # Display data with clickable links
                    st.subheader("📋 Results")
                    
                    # Convert the dataframe for better display
                    # Don't use markdown links, just show the actual data
                    display_df = df.copy()
                    
                    # Display the dataframe with proper column configuration
                    column_config = {
                        "Username": st.column_config.TextColumn("Username"),
                        "Message Link": st.column_config.LinkColumn("Message Link"),
                        "Group Name": st.column_config.TextColumn("Group Name"),
                        "Matched Keyword": st.column_config.TextColumn("Keyword"),
                        "Date": st.column_config.DatetimeColumn("Date"),
                        "Message Preview": st.column_config.TextColumn("Preview", width="large")
                    }
                    
                    # Only add Total Messages column when duplicates are not allowed
                    if not allow_duplicates:
                        column_config["Total Messages"] = st.column_config.NumberColumn("Total Messages", help="Total messages from this user")
                    
                    st.dataframe(
                        display_df,
                        use_container_width=True,
                        height=400,
                        column_config=column_config
                    )
                    
                    # Add info about clickable links
                    st.info("💡 Click on the Message Link column to open messages in Telegram")
                    
                    # Download options
                    st.subheader("📥 Download Results")
                    
                    if download_format == "Excel (.xlsx)":
                        # Save to Excel
                        excel_filename = f"telegram_scrape_{group.title.replace(' ', '_')}.xlsx"
                        df.to_excel(excel_filename, index=False)
                        
                        with open(excel_filename, "rb") as file:
                            st.download_button(
                                label="📥 Download Excel File",
                                data=file.read(),
                                file_name=excel_filename,
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                type="primary"
                            )
                    else:
                        # Save to CSV
                        csv_filename = f"telegram_scrape_{group.title.replace(' ', '_')}.csv"
                        csv_data = df.to_csv(index=False)
                        
                        st.download_button(
                            label="📥 Download CSV File",
                            data=csv_data,
                            file_name=csv_filename,
                            mime="text/csv",
                            type="primary"
                        )
                else:
                    st.warning("⚠️ No messages found matching the specified criteria.")
                    st.info("💡 Try:")
                    st.info("• Different keywords")
                    st.info("• Remove or change exclude keywords")
                    st.info("• Increase message limit")
                    st.info("• Disable case sensitive search")
                    
            except Exception as e:
                st.error(f"❌ Error occurred: {str(e)}")
                if "Could not find the input entity" in str(e):
                    st.error("🔗 Invalid group link. Please check the link and try again.")
                elif "FLOOD_WAIT" in str(e):
                    st.error("⏱️ Rate limited by Telegram. Please wait a few minutes and try again.")

        # Run the scraping
        asyncio.run(scrape_keywords())

# Footer
st.markdown("---")
st.markdown("💡 **Tips:**")
st.markdown("• Use public group links or invite links")
st.markdown("• Separate multiple keywords with commas")
st.markdown("• Higher message limits take longer to process")
st.markdown("• Results are exported to Excel format")






import streamlit as st
import asyncio
import pandas as pd
import os
import unicodedata
import re
import io
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
                                        min_value=100, max_value=50000, value=10000, step=500,
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
        
        # Define async scraping logic
        async def scrape_keywords():
            try:
                # Create client using session from secrets or generate new one
                if SESSION_STRING:
                    client = TelegramClient(StringSession(SESSION_STRING), int(API_ID), API_HASH, connection_retries=5, retry_delay=1)
                else:
                    client = TelegramClient(StringSession(), int(API_ID), API_HASH, connection_retries=5, retry_delay=1)
                
                with st.spinner("🔌 Connecting to Telegram..."):
                    await client.start()
                st.success("✅ Connected to Telegram!")
                
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

                st.info("📥 Starting message scan...")
                progress_bar = st.progress(0)
                status_text = st.empty()

                user_message_count = {}
                user_latest_message = {}
                user_messages = {}
                message_count = 0
                matches_found = 0
                
                if any('\u0590' <= char <= '\u05FF' for keyword in keywords for char in keyword):
                    st.info("🔤 Hebrew text detected - Using enhanced Unicode search")
                
                try:
                    async for msg in client.iter_messages(group, limit=message_limit):
                        message_count += 1
                        
                        if message_count % 50 == 0:
                            progress = min(message_count / message_limit, 1.0)
                            progress_bar.progress(progress)
                            status_text.text(f"📥 Scanned: {message_count:,} messages | Found: {matches_found} matches")
                        
                        if message_count % 100 == 0:
                            await asyncio.sleep(0.1)
                        
                        if msg.text and msg.sender:
                            normalized_msg_text = normalize_text(msg.text)
                            text_to_search = normalized_msg_text if case_sensitive else normalized_msg_text.lower()
                            
                            normalized_keywords = [normalize_text(k) for k in keywords]
                            keywords_to_check = normalized_keywords if case_sensitive else [k.lower() for k in normalized_keywords]
                        
                            normalized_exclude = [normalize_text(k) for k in exclude_keywords] if exclude_keywords else []
                            exclude_to_check = normalized_exclude if case_sensitive else [k.lower() for k in normalized_exclude]
                            
                            include_match = any(word in text_to_search for word in keywords_to_check)
                            exclude_match = any(word in text_to_search for word in exclude_to_check) if exclude_to_check else False
                            
                            if include_match and not exclude_match:
                                matches_found += 1
                                username = msg.sender.username if msg.sender.username else f"ID_{msg.sender.id}"
                                user_id = msg.sender.id
                                
                                user_message_count[user_id] = user_message_count.get(user_id, 0) + 1
                            
                                matched_keyword = next((orig_kw for orig_kw, norm_kw in zip(keywords, keywords_to_check) if norm_kw in text_to_search), keywords[0])
                            
                                msg_link = f"https://t.me/c/{str(group.id)[4:]}/{msg.id}" if str(group.id).startswith("-100") else f"{group_link}/{msg.id}"
                                msg_date = msg.date.strftime("%Y-%m-%d %H:%M:%S") if msg.date else "N/A"
                            
                                clean_text = msg.text.replace('\n', ' ').replace('\r', ' ')
                                clean_text = ''.join(char for char in clean_text if ord(char) < 65536)
                                preview_text = clean_text[:100] + "..." if len(clean_text) > 100 else clean_text
                                
                                message_data = [f"@{username}", matched_keyword, group.title, msg_link, msg_date, preview_text, 0]
                                
                                if user_id not in user_messages:
                                    user_messages[user_id] = []
                                user_messages[user_id].append(message_data)
                                
                                if user_id not in user_latest_message or msg.date > user_latest_message[user_id]['date']:
                                    user_latest_message[user_id] = {'data': message_data, 'date': msg.date, 'user_id': user_id}
                
                except Exception as e:
                    error_message = str(e)
                    st.error(f"❌ An error occurred: {error_message}")
                    
                    if "Could not find the input entity" in error_message:
                        st.error("🔗 This seems to be an invalid group/channel link.")
                        st.info("💡 Please check the link and ensure you are a member of the group/channel if it's private.")
                    elif "No user has" in error_message and "as username" in error_message:
                        st.error(f"👤 The username `{group_link}` does not seem to exist or has been changed.")
                        st.info("💡 Please double-check the username. If it's correct, the channel may have become private or been deleted.")
                    elif "FLOOD_WAIT" in error_message:
                        st.error("⏱️ Rate limited by Telegram. Please wait a few minutes before trying again.")
                    else:
                        st.info("💡 An unexpected error occurred. This could be due to a temporary network issue or an invalid link.")

                await client.disconnect()
                progress_bar.progress(1.0)
                status_text.text(f"✅ Scan complete! {message_count:,} messages scanned")
                
                final_data = []
                if allow_duplicates:
                    for user_id, messages in user_messages.items():
                        total_count = user_message_count.get(user_id, 0)
                        for msg_data in messages:
                            msg_data[6] = total_count
                            final_data.append(msg_data)
                    columns = ["Username", "Matched Keyword", "Group Name", "Message Link", "Date", "Message Preview"]
                    final_data = [row[:-1] for row in final_data]
                else:
                    for user_id, msg_info in user_latest_message.items():
                        msg_data = msg_info['data'].copy()
                        msg_data[6] = user_message_count.get(user_id, 0)
                        final_data.append(msg_data)
                    columns = ["Username", "Matched Keyword", "Group Name", "Message Link", "Date", "Message Preview", "Total Messages"]
                
                if final_data:
                    df = pd.DataFrame(final_data, columns=columns)
                    
                    st.success(f"🎉 **Scraping Complete!** Found **{len(df)}** matching messages")
                    
                    if not allow_duplicates:
                        st.info(f"📊 **Duplicate filtering applied**: {len(df)} unique users (latest message only)")
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("📊 Total Messages Scanned", f"{message_count:,}")
                    with col2:
                        st.metric("🎯 Matches Found", f"{len(df):,}")
                    with col3:
                        match_rate = (len(df) / message_count * 100) if message_count > 0 else 0
                        st.metric("📈 Match Rate", f"{match_rate:.2f}%")
                    
                    # Display results with clickable usernames
                    st.subheader("📋 Results")
                    
                    # First display the normal dataframe with message links
                    display_df = df.copy()
                    
                    # Show dataframe with message links
                    column_config = {
                        "Username": st.column_config.TextColumn("Username"),
                        "Message Link": st.column_config.LinkColumn("Message Link", display_text="View Message"),
                        "Group Name": st.column_config.TextColumn("Group Name"),
                        "Matched Keyword": st.column_config.TextColumn("Keyword"),
                        "Date": st.column_config.DatetimeColumn("Date"),
                        "Message Preview": st.column_config.TextColumn("Preview", width="large")
                    }
                    if not allow_duplicates:
                        column_config["Total Messages"] = st.column_config.NumberColumn("Total Messages", help="Total messages from this user")
                    
                    st.dataframe(display_df, use_container_width=True, height=400, column_config=column_config)
                    
                    # Now create a section with clickable username links
                    st.subheader("👤 Clickable Usernames")
                    st.info("💡 Click on any username below to open the Telegram profile:")
                    
                    # Create columns for username links in rows of 4
                    usernames = display_df['Username'].unique()
                    
                    # Create rows of 4 columns each
                    for i in range(0, len(usernames), 4):
                        cols = st.columns(4)
                        for j in range(4):
                            if i+j < len(usernames):
                                username = usernames[i+j]
                                if username.startswith('@') and not username.startswith('@ID_'):
                                    # Regular username format: @username
                                    user_url = f"https://t.me/{username[1:]}"
                                elif username.startswith('@ID_'):
                                    # ID format: @ID_123456789
                                    user_id = username[4:]  # Extract ID after '@ID_'
                                    user_url = f"https://t.me/c/{user_id}"
                                else:
                                    # Any other format
                                    clean_username = username.replace('@', '')
                                    user_url = f"https://t.me/{clean_username}"
                                
                                cols[j].markdown(f"[{username}]({user_url})")
                    
                    st.info("💡 Click on the 'View Message' links in the table above to open specific messages in Telegram.")
                    
                    st.subheader("📥 Download Results")
                    
                    if download_format == "Excel (.xlsx)":
                        excel_filename = f"telegram_scrape_{group.title.replace(' ', '_')}.xlsx"
                        output = io.BytesIO()
                        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                            df.to_excel(writer, index=False, sheet_name='Results')
                            workbook = writer.book
                            worksheet = writer.sheets['Results']
                            url_format = workbook.add_format({'font_color': 'blue', 'underline': 1})
                            try:
                                username_col_idx = df.columns.get_loc('Username')
                                msg_link_col_idx = df.columns.get_loc('Message Link')
                            except KeyError:
                                username_col_idx, msg_link_col_idx = -1, -1

                            for row_num, row_data in df.iterrows():
                                if username_col_idx != -1:
                                    username = row_data['Username']
                                    # Handle different username formats
                                    if username.startswith('@') and not username.startswith('@ID_'):
                                        # Regular username format: @username
                                        user_url = f"https://t.me/{username[1:]}"
                                        worksheet.write_url(row_num + 1, username_col_idx, user_url, url_format, username)
                                    elif username.startswith('@ID_'):
                                        # ID format: @ID_123456789
                                        user_id = username[4:]  # Extract ID after '@ID_'
                                        user_url = f"https://t.me/c/{user_id}"
                                        worksheet.write_url(row_num + 1, username_col_idx, user_url, url_format, username)
                                    else:
                                        # Any other format, try to make it clickable if possible
                                        clean_username = username.replace('@', '')
                                        user_url = f"https://t.me/{clean_username}"
                                        worksheet.write_url(row_num + 1, username_col_idx, user_url, url_format, username)
                                
                                if msg_link_col_idx != -1:
                                    worksheet.write_url(row_num + 1, msg_link_col_idx, row_data['Message Link'], url_format, 'View Message')
                        
                        excel_data = output.getvalue()
                        st.download_button("📥 Download Excel File", excel_data, excel_filename, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", type="primary")
                    else:
                        csv_filename = f"telegram_scrape_{group.title.replace(' ', '_')}.csv"
                        csv_data = df.to_csv(index=False)
                        st.download_button("📥 Download CSV File", csv_data, csv_filename, "text/csv", type="primary")
                else:
                    st.warning("⚠️ No messages found matching the specified criteria.")
                    st.info("💡 Try: Different keywords, removing exclude keywords, increasing message limit, or disabling case sensitive search.")
                    
            except Exception as e:
                st.error(f"❌ Error occurred: {str(e)}")
                if "Could not find the input entity" in str(e):
                    st.error("🔗 Invalid group link. Please check the link and try again.")
                elif "FLOOD_WAIT" in str(e):
                    st.error("⏱️ Rate limited by Telegram. Please wait a few minutes and try again.")

        asyncio.run(scrape_keywords())

# Footer
st.markdown("---")
st.markdown("💡 **Tips:**")
st.markdown("• Use public group links or invite links.")
st.markdown("• Separate multiple keywords with commas.")
st.markdown("• Higher message limits take longer to process.")
st.markdown("• For Hebrew text: Copy keywords directly from Telegram messages.")
st.markdown("• If scan stops early, try smaller message limits (5K-10K).")


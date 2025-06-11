import streamlit as st
import asyncio
import pandas as pd
import os
from dotenv import load_dotenv
from telethon.sync import TelegramClient
from telethon.tl.functions.messages import GetDialogsRequest
from telethon.tl.types import InputPeerEmpty

# Load environment variables
load_dotenv()

# Get API credentials from environment variables
API_ID = os.getenv('TELEGRAM_API_ID')
API_HASH = os.getenv('TELEGRAM_API_HASH')

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
keywords_input = st.text_input("🔍 Enter keywords (comma-separated, e.g. massage, עיסוי)")

# Advanced options
with st.expander("⚙️ Advanced Options"):
    message_limit = st.number_input("📊 Maximum messages to scan", min_value=100, max_value=50000, value=10000, step=500)
    case_sensitive = st.checkbox("🔤 Case sensitive search")

if st.button("🚀 Start Scraping", type="primary"):
    if not all([group_link, keywords_input]):
        st.error("❌ Please fill in all fields.")
    else:
        keywords = [k.strip() for k in keywords_input.split(",")]
        
        # Define async scraping logic
        async def scrape_keywords():
            try:
                # Create client using existing session
                client = TelegramClient(
                    'session', 
                    int(API_ID), 
                    API_HASH,
                    connection_retries=5,
                    retry_delay=1
                )
                
                with st.spinner("🔌 Connecting to Telegram..."):
                    await client.start()
                st.success("✅ Connected to Telegram!")
                
                with st.spinner("🔍 Getting group information..."):
                    group = await client.get_entity(group_link)
                st.success(f"✅ Found group: **{group.title}**")
                st.info(f"👥 Group members: {group.participants_count if hasattr(group, 'participants_count') else 'N/A'}")

                # Progress tracking
                st.info("📥 Starting message scan...")
                progress_bar = st.progress(0)
                status_text = st.empty()

                data = []
                message_count = 0
                matches_found = 0
                
                async for msg in client.iter_messages(group, limit=message_limit):
                    message_count += 1
                    
                    # Update progress every 50 messages
                    if message_count % 50 == 0:
                        progress = min(message_count / message_limit, 1.0)
                        progress_bar.progress(progress)
                        status_text.text(f"📥 Scanned: {message_count:,} messages | Found: {matches_found} matches")
                    
                    if msg.text:
                        # Check for keyword matches
                        text_to_search = msg.text if case_sensitive else msg.text.lower()
                        keywords_to_check = keywords if case_sensitive else [k.lower() for k in keywords]
                        
                        if any(word in text_to_search for word in keywords_to_check):
                            matches_found += 1
                            username = msg.sender.username if msg.sender and msg.sender.username else "N/A"
                            
                            # Find which keyword matched
                            matched_keyword = next((
                                orig_kw for orig_kw, check_kw in zip(keywords, keywords_to_check) 
                                if check_kw in text_to_search
                            ), keywords[0])
                            
                            # Create message link
                            msg_link = (
                                f"https://t.me/c/{str(group.id)[4:]}/{msg.id}"
                                if str(group.id).startswith("-100")
                                else f"{group_link}/{msg.id}"
                            )
                            
                            # Get message date
                            msg_date = msg.date.strftime("%Y-%m-%d %H:%M:%S") if msg.date else "N/A"
                            
                            data.append([
                                f"@{username}", 
                                matched_keyword, 
                                group.title, 
                                msg_link, 
                                msg_date,
                                msg.text[:100] + "..." if len(msg.text) > 100 else msg.text
                            ])

                await client.disconnect()
                progress_bar.progress(1.0)
                status_text.text(f"✅ Scan complete! {message_count:,} messages scanned")
                
                if data:
                    df = pd.DataFrame(data, columns=[
                        "Username", 
                        "Matched Keyword", 
                        "Group Name", 
                        "Message Link", 
                        "Date",
                        "Message Preview"
                    ])
                    
                    # Save to Excel
                    excel_filename = f"telegram_scrape_{group.title.replace(' ', '_')}.xlsx"
                    df.to_excel(excel_filename, index=False)
                    
                    # Display results
                    st.success(f"🎉 **Scraping Complete!** Found **{len(data)}** matching messages")
                    
                    # Stats
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("📊 Total Messages", f"{message_count:,}")
                    with col2:
                        st.metric("🎯 Matches Found", len(data))
                    with col3:
                        st.metric("📈 Match Rate", f"{(len(data)/message_count)*100:.2f}%")
                    
                    # Display data
                    st.dataframe(df, use_container_width=True)
                    
                    # Download button
                    with open(excel_filename, "rb") as file:
                        st.download_button(
                            label="📥 Download Excel File",
                            data=file.read(),
                            file_name=excel_filename,
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            type="primary"
                        )
                else:
                    st.warning("⚠️ No messages found matching the specified keywords.")
                    st.info("💡 Try:")
                    st.info("• Different keywords")
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

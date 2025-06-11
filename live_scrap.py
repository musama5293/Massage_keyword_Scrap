import streamlit as st
import pandas as pd
import os
from dotenv import load_dotenv
import datetime
import requests
import time

load_dotenv()
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

st.title("🤖 Telegram Group Keyword Scraper (Bot Version)")

if not BOT_TOKEN:
    st.error("⚠️ Bot token not found! Please create a .env file with TELEGRAM_BOT_TOKEN")
    with st.expander("🔧 Quick Setup"):
        st.markdown("""
        1. Message @BotFather in Telegram
        2. Send `/newbot`
        3. Name: "My Scraper Bot"
        4. Username: "myscraper_bot"
        5. Copy token to `.env` file:
        ```
        TELEGRAM_BOT_TOKEN=your_bot_token_here
        ```
        """)
    st.stop()

st.success("✅ Ready to scrape!")

def join_group(invite_link):
    """Join group via invite link"""
    try:
        # Handle different link formats
        if "joinchat/" in invite_link:
            chat_id = invite_link
        elif "t.me/+" in invite_link:
            chat_id = invite_link
        else:
            # Public group username
            username = invite_link.replace("https://t.me/", "").replace("@", "")
            chat_id = f"@{username}"
        
        # Try to get chat info (this will work if bot can access the chat)
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/getChat"
        params = {'chat_id': chat_id}
        response = requests.get(url, params=params)
        
        if response.status_code == 200:
            return True, response.json()['result']
        
        # Try to join if it's an invite link
        if "joinchat/" in invite_link or "t.me/+" in invite_link:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/joinChat"
            params = {'chat_id': invite_link}
            response = requests.post(url, params=params)
            
            if response.status_code == 200:
                return True, response.json()['result']
        
        return False, "Could not join group"
        
    except Exception as e:
        return False, str(e)

def get_chat_updates(chat_id, timeout=30):
    """Get new messages from specific chat"""
    messages = []
    
    # Get updates for specified time
    start_time = time.time()
    processed_ids = set()
    
    while time.time() - start_time < timeout:
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
            params = {'timeout': 5, 'limit': 100}
            response = requests.get(url, params=params)
            
            if response.status_code == 200:
                updates = response.json().get('result', [])
                
                for update in updates:
                    if 'message' in update and 'text' in update['message']:
                        msg = update['message']
                        msg_id = msg['message_id']
                        
                        # Check if from target chat and not processed
                        if (str(msg['chat']['id']) == str(chat_id) and 
                            msg_id not in processed_ids):
                            
                            processed_ids.add(msg_id)
                            messages.append({
                                'text': msg['text'],
                                'username': msg.get('from', {}).get('username', 'Unknown'),
                                'date': datetime.datetime.fromtimestamp(msg['date']),
                                'message_id': msg_id
                            })
                
                # Clear processed updates
                if updates:
                    last_update_id = updates[-1]['update_id']
                    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
                    params = {'offset': last_update_id + 1}
                    requests.get(url, params=params)
        
        except:
            time.sleep(1)
    
    return messages

# Main Interface (exactly like original app)
st.subheader("📥 Message Scraper")

group_link = st.text_input("🔗 Enter the Telegram group link (public or invite link)")
keywords_input = st.text_input("🔍 Enter keywords (comma-separated, e.g. massage, עיסוי)")

# Advanced options
with st.expander("⚙️ Advanced Options"):
    monitoring_time = st.number_input("⏰ Monitoring time (seconds)", min_value=10, max_value=300, value=60)
    case_sensitive = st.checkbox("🔤 Case sensitive search")

if st.button("🚀 Start Scraping", type="primary"):
    if not all([group_link, keywords_input]):
        st.error("❌ Please fill in all fields.")
    else:
        keywords = [k.strip() for k in keywords_input.split(",")]
        
        # Step 1: Join/Access Group
        with st.spinner("🔌 Connecting to group..."):
            success, result = join_group(group_link)
        
        if success:
            chat_info = result
            chat_id = chat_info['id']
            group_title = chat_info.get('title', chat_info.get('username', 'Unknown Group'))
            
            st.success(f"✅ Connected to group: **{group_title}**")
            
            # Step 2: Monitor Messages
            st.info(f"📥 Monitoring for {monitoring_time} seconds...")
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # Get messages
            start_time = time.time()
            all_messages = []
            matches_found = 0
            
            while time.time() - start_time < monitoring_time:
                elapsed = time.time() - start_time
                progress_bar.progress(elapsed / monitoring_time)
                
                # Get new messages
                new_messages = get_chat_updates(chat_id, timeout=5)
                all_messages.extend(new_messages)
                
                # Update status
                status_text.text(f"📥 Monitoring... {int(elapsed)}s elapsed | Found: {matches_found} matches | Messages: {len(all_messages)}")
                
                # Check for matches in new messages
                for msg in new_messages:
                    text = msg['text']
                    text_to_search = text if case_sensitive else text.lower()
                    keywords_to_check = keywords if case_sensitive else [k.lower() for k in keywords]
                    
                    if any(word in text_to_search for word in keywords_to_check):
                        matches_found += 1
                        # Show real-time match
                        st.success(f"🎯 Match found: '{text[:50]}...' by @{msg['username']}")
            
            progress_bar.progress(1.0)
            status_text.text(f"✅ Monitoring complete! {monitoring_time}s elapsed")
            
            # Process all matches
            data = []
            for msg in all_messages:
                text = msg['text']
                text_to_search = text if case_sensitive else text.lower()
                keywords_to_check = keywords if case_sensitive else [k.lower() for k in keywords]
                
                for i, word in enumerate(keywords_to_check):
                    if word in text_to_search:
                        username = msg['username'] or "N/A"
                        matched_keyword = keywords[i]  # Original case
                        msg_date = msg['date'].strftime("%Y-%m-%d %H:%M:%S")
                        
                        data.append([
                            f"@{username}",
                            matched_keyword,
                            group_title,
                            f"Message ID: {msg['message_id']}",
                            msg_date,
                            text[:100] + "..." if len(text) > 100 else text
                        ])
                        break
            
            if data:
                df = pd.DataFrame(data, columns=[
                    "User name", "Word", "Group", "Link to last message", "Date", "Message Preview"
                ])
                
                st.success(f"🎉 **Scraping Complete!** Found **{len(data)}** matching messages")
                
                # Stats (like original app)
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("📊 Total Messages", len(all_messages))
                with col2:
                    st.metric("🎯 Matches Found", len(data))
                with col3:
                    st.metric("📈 Match Rate", f"{(len(data)/max(len(all_messages), 1))*100:.1f}%")
                
                # Display results
                st.dataframe(df, use_container_width=True)
                
                # Download (like original app)
                excel_filename = f"telegram_scrape_{group_title.replace(' ', '_')}.xlsx"
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
                st.warning("⚠️ No messages found matching the specified keywords.")
                st.info("💡 Try:")
                st.info("• Different keywords")
                st.info("• Longer monitoring time")
                st.info("• Make sure group is active")
        
        else:
            st.error(f"❌ Could not access group: {result}")
            st.info("💡 Make sure:")
            st.info("• Group link is valid")
            st.info("• Group allows bots")
            st.info("• Bot has necessary permissions")

st.markdown("---")
st.markdown("💡 **Bot Features:**")
st.markdown("• ✅ **Auto-joins groups** via invite links")
st.markdown("• ✅ **No my.telegram.org** access needed")
st.markdown("• ✅ **Same interface** as original app")
st.markdown("• ❌ **Only new messages** (real-time monitoring)")
st.markdown("• 🔥 **Perfect for live groups**") 
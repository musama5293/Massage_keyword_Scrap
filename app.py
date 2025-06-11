import streamlit as st
import asyncio
import pandas as pd
import os
from dotenv import load_dotenv
from telethon.sync import TelegramClient
from telethon.tl.functions.messages import GetDialogsRequest
from telethon.tl.types import InputPeerEmpty
from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError, PhoneNumberInvalidError

# Load environment variables
load_dotenv()

# Get API credentials from environment variables
API_ID = os.getenv('TELEGRAM_API_ID')
API_HASH = os.getenv('TELEGRAM_API_HASH')

# Streamlit UI
st.title("Telegram Group Keyword Scraper")

# Check if API credentials are loaded
if not API_ID or not API_HASH:
    st.error("⚠️ API credentials not found! Please create a .env file with TELEGRAM_API_ID and TELEGRAM_API_HASH")
    st.stop()

st.success("✅ API credentials loaded successfully!")

# Initialize session state for authentication
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'phone_number' not in st.session_state:
    st.session_state.phone_number = ""
if 'awaiting_code' not in st.session_state:
    st.session_state.awaiting_code = False
if 'awaiting_password' not in st.session_state:
    st.session_state.awaiting_password = False

# Authentication Section
if not st.session_state.authenticated:
    st.subheader("🔐 Telegram Authentication")
    
    if not st.session_state.awaiting_code and not st.session_state.awaiting_password:
        phone_number = st.text_input("Enter your phone number (with country code, e.g., +923001234567):")
        if st.button("Send Verification Code"):
            if phone_number:
                st.session_state.phone_number = phone_number
                
                async def send_code():
                    try:
                        client = TelegramClient('session', int(API_ID), API_HASH)
                        await client.connect()
                        result = await client.send_code_request(phone_number)
                        await client.disconnect()
                        return True
                    except Exception as e:
                        st.error(f"Error sending code: {str(e)}")
                        return False
                
                if asyncio.run(send_code()):
                    st.session_state.awaiting_code = True
                    st.success("✅ Verification code sent to your phone!")
                    st.rerun()
    
    elif st.session_state.awaiting_code:
        st.info(f"📱 Verification code sent to: {st.session_state.phone_number}")
        verification_code = st.text_input("Enter the verification code:")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Verify Code"):
                if verification_code:
                    async def verify_code():
                        try:
                            client = TelegramClient('session', int(API_ID), API_HASH)
                            await client.connect()
                            await client.sign_in(st.session_state.phone_number, verification_code)
                            st.session_state.authenticated = True
                            st.session_state.awaiting_code = False
                            await client.disconnect()
                            return "success"
                        except SessionPasswordNeededError:
                            st.session_state.awaiting_code = False
                            st.session_state.awaiting_password = True
                            await client.disconnect()
                            return "password_needed"
                        except Exception as e:
                            await client.disconnect()
                            return f"error: {str(e)}"
                    
                    result = asyncio.run(verify_code())
                    if result == "success":
                        st.success("✅ Authentication successful!")
                        st.rerun()
                    elif result == "password_needed":
                        st.info("🔒 Two-factor authentication detected!")
                        st.rerun()
                    else:
                        st.error(f"❌ {result}")
        
        with col2:
            if st.button("Resend Code"):
                st.session_state.awaiting_code = False
                st.rerun()
    
    elif st.session_state.awaiting_password:
        st.info("🔒 Enter your two-factor authentication password:")
        password = st.text_input("2FA Password:", type="password")
        
        if st.button("Authenticate"):
            if password:
                async def verify_password():
                    try:
                        client = TelegramClient('session', int(API_ID), API_HASH)
                        await client.connect()
                        await client.sign_in(password=password)
                        st.session_state.authenticated = True
                        st.session_state.awaiting_password = False
                        await client.disconnect()
                        return True
                    except Exception as e:
                        await client.disconnect()
                        st.error(f"❌ Error: {str(e)}")
                        return False
                
                if asyncio.run(verify_password()):
                    st.success("✅ Authentication successful!")
                    st.rerun()

# Main App (only show if authenticated)
if st.session_state.authenticated:
    st.subheader("📥 Message Scraper")
    
    group_link = st.text_input("Enter the Telegram group link (public or invite link)")
    keywords_input = st.text_input("Enter keywords (comma-separated, e.g. massage, עיסוי)")

    if st.button("Start Scraping"):
        if not all([group_link, keywords_input]):
            st.error("Please fill in all fields.")
        else:
            keywords = [k.strip() for k in keywords_input.split(",")]
            
            # Define async scraping logic
            async def scrape_keywords():
                try:
                    client = TelegramClient(
                        'session', 
                        int(API_ID), 
                        API_HASH,
                        connection_retries=5,
                        retry_delay=1
                    )
                    
                    st.info("🔌 Connecting to Telegram...")
                    await client.start()
                    st.success("✅ Connected to Telegram!")
                    
                    st.info("🔍 Getting group information...")
                    group = await client.get_entity(group_link)
                    st.success(f"✅ Found group: {group.title}")

                    st.info("📥 Scraping messages...")
                    data = []
                    message_count = 0
                    progress_bar = st.progress(0)
                    
                    async for msg in client.iter_messages(group, limit=10000):
                        message_count += 1
                        if message_count % 100 == 0:
                            progress_bar.progress(min(message_count / 10000, 1.0))
                            st.info(f"📥 Processed {message_count} messages...")
                        
                        if msg.text and any(word.lower() in msg.text.lower() for word in keywords):
                            username = msg.sender.username if msg.sender and msg.sender.username else "N/A"
                            keyword_used = next((word for word in keywords if word.lower() in msg.text.lower()), None)
                            msg_link = (
                                f"https://t.me/c/{str(group.id)[4:]}/{msg.id}"
                                if str(group.id).startswith("-100")
                                else f"{group_link}/{msg.id}"
                            )
                            data.append([f"@{username}", keyword_used, group_link, msg_link])

                    await client.disconnect()
                    
                    if data:
                        df = pd.DataFrame(data, columns=["User name", "Word", "Group", "Link to last message"])
                        df.to_excel("telegram_scrape.xlsx", index=False)
                        st.success(f"✅ Scraping complete! Found {len(data)} matching messages.")
                        st.dataframe(df)
                        
                        # Download button
                        with open("telegram_scrape.xlsx", "rb") as file:
                            st.download_button(
                                label="📥 Download Excel File",
                                data=file.read(),
                                file_name="telegram_scrape.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                            )
                    else:
                        st.warning("⚠️ No messages found matching the specified keywords.")
                        
                except Exception as e:
                    st.error(f"❌ Error occurred: {str(e)}")

            asyncio.run(scrape_keywords())

    # Session management
    st.sidebar.subheader("🔧 Session Management")
    if st.sidebar.button("🚪 Logout"):
        st.session_state.authenticated = False
        st.session_state.awaiting_code = False
        st.session_state.awaiting_password = False
        st.session_state.phone_number = ""
        if os.path.exists("session.session"):
            os.remove("session.session")
        st.success("✅ Logged out successfully!")
        st.rerun()

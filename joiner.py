#!/usr/bin/env python3
"""
Standalone Group Joiner Module
Session wali ID se direct group join karne ke liye
Supports: DM me link bhejne par auto-join
"""

import re
import logging
from pyrogram import filters
from pyrogram.types import Message
from pyrogram.errors import (
    UserAlreadyParticipant,
    UsernameInvalid,
    InviteHashExpired,
    InviteHashInvalid,
    FloodWait,
    PeerIdInvalid
)

# Existing code se import
from clients import bot, assistant
from config import OWNER_ID

logger = logging.getLogger(__name__)

# ================= DECORATORS =================
def owner_only(func):
    """Owner only decorator"""
    from functools import wraps
    @wraps(func)
    async def wrapper(client, message):
        if not message.from_user:
            return
        if message.from_user.id != OWNER_ID:
            return await message.reply("⛔ **Owner only command!**")
        return await func(client, message)
    return wrapper


# ================= CORE JOIN FUNCTION =================
async def join_chat_by_input(input_data: str, status_msg: Message = None) -> dict:
    """
    Core join function - join any chat by link/username/chat_id
    Returns: dict with success status and chat info
    """
    result = {
        "success": False,
        "chat": None,
        "error": None,
        "join_method": "Unknown",
        "is_request": False
    }
    
    try:
        chat = None
        join_method = "Unknown"

        # =============================================
        # CASE 1: Numeric Chat ID
        # =============================================
        if input_data.startswith("-") or input_data.isdigit():
            join_method = "Chat ID"
            chat_id = int(input_data)
            
            try:
                chat = await assistant.join_chat(chat_id)
            except UserAlreadyParticipant:
                chat = await assistant.get_chat(chat_id)
                result["error"] = "already_joined"
                return result

        # =============================================
        # CASE 2: Private Invite Link (+ or joinchat)
        # =============================================
        elif "+" in input_data or "joinchat/" in input_data:
            join_method = "Private Link"
            
            # Extract invite hash
            if "+" in input_data:
                hash_key = input_data.split("+")[-1].strip()
            else:
                hash_key = input_data.split("joinchat/")[-1].strip()
            
            # Clean hash
            hash_key = re.sub(r'[^a-zA-Z0-9_\-]', '', hash_key)
            
            if not hash_key:
                result["error"] = "invalid_hash"
                return result
            
            try:
                chat = await assistant.join_chat(hash_key)
            except UserAlreadyParticipant:
                chat = await assistant.get_chat(hash_key)
                result["error"] = "already_joined"
                return result

        # =============================================
        # CASE 3: Public Link or Username
        # =============================================
        else:
            join_method = "Public/Username"
            
            # Check if it's a t.me link
            if "t.me" in input_data or "telegram.me" in input_data:
                username_match = re.search(
                    r'(?:t\.me|telegram\.me)/(?:s/)?([a-zA-Z0-9_]{5,32})',
                    input_data
                )
                if username_match:
                    username = username_match.group(1)
                else:
                    username = input_data.split("/")[-1].replace("@", "").strip().split("?")[0]
            else:
                username = input_data.replace("@", "").strip()
            
            try:
                chat = await assistant.join_chat(username)
            except UserAlreadyParticipant:
                chat = await assistant.get_chat(username)
                result["error"] = "already_joined"
                return result

        # =============================================
        # SUCCESS
        # =============================================
        if chat:
            result["success"] = True
            result["chat"] = chat
            result["join_method"] = join_method
            
            # Get chat info
            chat_title = getattr(chat, 'title', 'Unknown')
            chat_id = getattr(chat, 'id', 'Unknown')
            
            # Check chat type
            chat_type = "Channel" if hasattr(chat, 'type') and 'channel' in str(chat.type).lower() else "Group"
            
            # Get username if available
            username_display = "Private"
            try:
                chat_info = await assistant.get_chat(chat_id)
                if hasattr(chat_info, 'username') and chat_info.username:
                    username_display = f"@{chat_info.username}"
            except:
                pass
            
            result["chat_info"] = {
                "title": chat_title,
                "id": chat_id,
                "type": chat_type,
                "username": username_display
            }
            
            return result

    # =============================================
    # ERROR HANDLING
    # =============================================
    except FloodWait as e:
        result["error"] = "flood"
        result["wait_time"] = e.x
        return result
        
    except InviteHashExpired:
        result["error"] = "expired"
        return result
        
    except InviteHashInvalid:
        result["error"] = "invalid_hash"
        return result
        
    except UsernameInvalid:
        result["error"] = "invalid_username"
        return result
        
    except UserAlreadyParticipant:
        result["error"] = "already_joined"
        return result
        
    except Exception as e:
        error_str = str(e).lower()
        
        # Check for join request (pending approval)
        if any(keyword in error_str for keyword in ['request', 'approval', 'wait', 'pending', 'need']):
            result["error"] = "join_request"
            result["request_data"] = input_data
            return result
        
        result["error"] = "unknown"
        result["error_msg"] = str(e)
        return result
    
    return result


# ================= COMMAND: /joingroup =================
@bot.on_message(filters.command("joingroup") & filters.private)
@owner_only
async def join_group_cmd(client, message: Message):
    """
    Session account se group/channel join karein
    Supports: Private Links, Public Links, Usernames, Chat IDs
    """
    if len(message.command) < 2:
        return await message.reply(
            "❌ **Usage:**\n"
            "• `/joingroup https://t.me/+abc123` (Private Link)\n"
            "• `/joingroup https://t.me/joinchat/abc123` (Private Link)\n"
            "• `/joingroup https://t.me/publicgroup` (Public Link)\n"
            "• `/joingroup @publicgroup` (Username)\n"
            "• `/joingroup -100123456789` (Chat ID)"
        )

    input_data = message.command[1].strip()
    status_msg = await message.reply("🔄 **Joining group using session account...**")
    
    # Call core join function
    result = await join_chat_by_input(input_data, status_msg)
    
    # =============================================
    # Handle Results
    # =============================================
    if result["success"]:
        info = result["chat_info"]
        await status_msg.edit(
            f"✅ **Successfully Joined!**\n\n"
            f"📋 **Type:** {info['type']}\n"
            f"📋 **Name:** {info['title']}\n"
            f"👤 **Username:** {info['username']}\n"
            f"🆔 **Chat ID:** `{info['id']}`\n"
            f"🔗 **Method:** {result['join_method']}\n\n"
            f"💡 **Next Steps:**\n"
            f"• Use `/join {info['id']}` to start forwarding\n"
            f"• Use `/leave` to stop forwarding"
        )
        logger.info(f"✅ Joined: {info['title']} ({info['id']})")
        
    elif result["error"] == "already_joined":
        await status_msg.edit("ℹ️ **Session account already joined this chat!**")
        
    elif result["error"] == "flood":
        wait_time = result["wait_time"]
        minutes = wait_time // 60
        seconds = wait_time % 60
        time_str = f"{minutes}m {seconds}s" if minutes > 0 else f"{seconds}s"
        await status_msg.edit(f"⚠️ **Flood Wait!** Please wait **{time_str}** before trying again.")
        
    elif result["error"] == "expired":
        await status_msg.edit("❌ **Invite Link Expired!** Please ask for a new invite link.")
        
    elif result["error"] == "invalid_hash":
        await status_msg.edit("❌ **Invalid Invite Link!** Please check the link and try again.")
        
    elif result["error"] == "invalid_username":
        await status_msg.edit("❌ **Invalid Username!** The username or public link is invalid.")
        
    elif result["error"] == "join_request":
        await status_msg.edit(
            f"📨 **Join Request Sent!**\n\n"
            f"🔗 **Link:** `{input_data}`\n"
            f"📋 **Type:** 🔵 Request Link (Needs Admin Approval)\n\n"
            f"────────────────────\n"
            f"⏳ **Status:** Pending Approval\n\n"
            f"💡 **What happens next:**\n"
            f"• Admin will review your join request\n"
            f"• You'll be notified when approved\n"
            f"• After approval, use `/join <chat_id>`\n\n"
            f"⚠️ **Note:** This may take some time depending on admin."
        )
        
    else:
        error_msg = result.get("error_msg", "Unknown error")
        await status_msg.edit(f"❌ **Error Occurred!**\n\n`{error_msg[:300]}`")


# ================= DM AUTO-JOIN HANDLER =================
@bot.on_message(filters.private & filters.text & ~filters.command(["start", "help", "joingroup", "status"]))
async def auto_join_from_dm(client, message: Message):
    """
    DM mein link bhejne par auto-join
    """
    # Only owner can use this
    if not message.from_user or message.from_user.id != OWNER_ID:
        return
    
    input_data = message.text.strip()
    
    # Check if it looks like a Telegram link or username
    is_tg_link = (
        "t.me" in input_data or 
        "telegram.me" in input_data or 
        input_data.startswith("@") or
        input_data.startswith("-") or
        input_data.isdigit()
    )
    
    if not is_tg_link:
        return
    
    # Check if it's a valid joinable format
    if not any([
        "t.me" in input_data,
        "telegram.me" in input_data,
        input_data.startswith("@"),
        input_data.startswith("-"),
        input_data.isdigit()
    ]):
        return
    
    status_msg = await message.reply("🔄 **Auto-joining via DM...**")
    
    # Call core join function
    result = await join_chat_by_input(input_data, status_msg)
    
    # =============================================
    # Handle Results
    # =============================================
    if result["success"]:
        info = result["chat_info"]
        await status_msg.edit(
            f"✅ **Auto-Joined from DM!**\n\n"
            f"📋 **Type:** {info['type']}\n"
            f"📋 **Name:** {info['title']}\n"
            f"👤 **Username:** {info['username']}\n"
            f"🆔 **Chat ID:** `{info['id']}`\n"
            f"🔗 **Method:** {result['join_method']}\n\n"
            f"💡 **Next Steps:**\n"
            f"• Use `/join {info['id']}` to start forwarding"
        )
        logger.info(f"✅ Auto-joined from DM: {info['title']} ({info['id']})")
        
    elif result["error"] == "already_joined":
        await status_msg.edit("ℹ️ **Already joined this chat!**")
        
    elif result["error"] == "flood":
        wait_time = result["wait_time"]
        minutes = wait_time // 60
        seconds = wait_time % 60
        time_str = f"{minutes}m {seconds}s" if minutes > 0 else f"{seconds}s"
        await status_msg.edit(f"⚠️ **Flood Wait!** Please wait **{time_str}** before trying again.")
        
    elif result["error"] == "expired":
        await status_msg.edit("❌ **Invite Link Expired!**")
        
    elif result["error"] == "invalid_hash":
        await status_msg.edit("❌ **Invalid Invite Link!**")
        
    elif result["error"] == "invalid_username":
        await status_msg.edit("❌ **Invalid Username!**")
        
    elif result["error"] == "join_request":
        await status_msg.edit(
            f"📨 **Join Request Sent!**\n\n"
            f"🔗 **Link:** `{input_data}`\n"
            f"⏳ **Status:** Pending Admin Approval\n\n"
            f"💡 Wait for admin to approve your request."
        )
        
    else:
        error_msg = result.get("error_msg", "Unknown error")
        await status_msg.edit(f"❌ **Error:** `{error_msg[:200]}`")


# ================= STATUS CHECK COMMAND =================
@bot.on_message(filters.command("sessionstatus") & filters.private)
@owner_only
async def session_status_cmd(client, message: Message):
    """Check session account status"""
    try:
        me = await assistant.get_me()
        
        # Count joined chats
        chat_count = 0
        async for _ in assistant.get_dialogs():
            chat_count += 1
        
        await message.reply(
            f"📊 **Session Account Status**\n\n"
            f"👤 **Account:** @{me.username}\n"
            f"🆔 **User ID:** `{me.id}`\n"
            f"📋 **Total Chats:** {chat_count}\n"
            f"🔄 **Status:** 🟢 Online\n\n"
            f"💡 Send any group link in DM to auto-join!"
        )
    except Exception as e:
        await message.reply(f"❌ Error getting status: {e}")

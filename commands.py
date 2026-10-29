from functools import wraps
from pyrogram import filters
from pyrogram.types import Message
from pyrogram.errors import (
    UserAlreadyParticipant,
    UserNotParticipant,
    ChatAdminRequired,
    ChannelInvalid,
    PeerIdInvalid,
)
import asyncio
import logging

from clients import bot, assistant
from config import OWNER_ID

from db import (
    add_sudoer,
    del_sudoer,
    get_sudoers,
    is_sudoer,
)

from room_state import (
    get_room,
    get_recent_play_room,
    get_play_rooms,
)
from audio_engine import (
    set_volume,
    set_gain,
    set_bass,
    set_treble,
    get_audio_levels,
    set_voice_mode,
    get_voice_mode,
)
import bridge

logger = logging.getLogger(__name__)


# ================= VC JOIN FAILED MESSAGE =================
VC_JOIN_FAIL_MSG = (
    "❌ **VC join failed.**\n\n"
    "**Vc chalu hai kya ye dekho** 👀\n"
    "Ya tumhari id group me join hai? **Join nhi hai to us id ko join krao** — "
    "VC pr nhi, **group me link se join kro** fir command chlao.\n\n"
    "✅ **Vc join ho jayega.**"
)


async def send_vc_join_error(message: Message, error: Exception = None):
    """Send the standard VC-join-failed message with optional error detail."""
    text = VC_JOIN_FAIL_MSG
    if error:
        logger.exception("VC join failed: %s", error)
        text += f"\n\n`{type(error).__name__}: {error}`"
    try:
        await message.reply(text)
    except Exception:
        logger.exception("Failed to send VC join error message")


# ================= VC JOIN WRAPPER =================
def handle_vc_join(func):
    """
    Wrap a command that joins the assistant to a VC.
    On any join-related failure, reply with the Hinglish hint message.
    """
    @wraps(func)
    async def wrapper(client, message, *args, **kwargs):
        try:
            return await func(client, message, *args, **kwargs)
        except UserAlreadyParticipant:
            await message.reply("ℹ️ Assistant already VC me hai.")
        except (UserNotParticipant, ChatAdminRequired,
                ChannelInvalid, PeerIdInvalid) as e:
            await send_vc_join_error(message, e)
        except Exception as e:
            await send_vc_join_error(message, e)
    return wrapper


# ================= OWNER ONLY DECORATOR =================
def owner_only(func):
    @wraps(func)
    async def wrapper(client, message):
        if not message.from_user:
            return
        uid = message.from_user.id
        if uid != OWNER_ID and not await is_sudoer(uid):
            return await message.reply("⛔ Owner/Sudo only")
        return await func(client, message)
    return wrapper


# ================= HELP COMMAND =================
@bot.on_message(filters.command("help"))
async def help_cmd(_, message: Message):
    text = """
🎧 **VC Audio Relay Bot (ULTRA TUNED AUDIO ENGINE)**

━━━━━━━━━━━━━━━━━━
🎙 **Voice Chat Controls**

`/join -100xxxxxxxx` ➜ VC join (chat ID only)
`/joingroup <chat_id | @username | link>` ➜ Join group (no VC)
`/leave` ➜ Leave current VC
`/record` ➜ Start/stop recording
`/listvc` ➜ Show all active VCs

━━━━━━━━━━━━━━━━━━
🎛 **Audio Controls**

`/volume <0-400>`   (default 200)
`/gain <0-150>`     (default 30)
`/bass <0-100>`     (default 10)
`/treble <0-100>`   (default 40)

`/voice female|male|normal`
  • female → sharp, thin (treble 70, bass 5)
  • male   → heavy, bassy (bass 60, treble 15)
  • normal → balanced

`/mute` / `/unmute`  – master mute/unmute (only command works)

`/automute on|off` – auto‑mute on join

━━━━━━━━━━━━━━━━━━
📊 **Status & Broadcast**

`/status` – show current settings + active VCs
`/broadcast <text>` – send message to all active VCs

━━━━━━━━━━━━━━━━━━
👑 **Sudo Management**

`/sudoadd <user_id>` or reply to user
`/sudodel <user_id>` or reply to user
`/sudolist` – list sudo users

━━━━━━━━━━━━━━━━━━
🚀 **ULTRA HARDWARE-MAXIMIZING SATURATOR IS ACTIVE.**
"""
    await message.reply_text(text)


# ================= VOLUME =================
@bot.on_message(filters.command("volume"))
@owner_only
async def volume_cmd(_, message):
    try:
        if len(message.command) < 2:
            return await message.reply("Usage: /volume 0-400")
        level = int(message.command[1])
        if level < 0 or level > 400:
            return await message.reply("❌ Volume Range: 0-400")
        set_volume(level)
        await message.reply(f"🚀 Volume: {level}/400")
    except ValueError:
        await message.reply("❌ Only numbers! Example: /volume 200")


# ================= GAIN =================
@bot.on_message(filters.command("gain"))
@owner_only
async def gain_cmd(_, message):
    try:
        if len(message.command) < 2:
            return await message.reply("Usage: /gain 0-150")
        level = int(message.command[1])
        if level < 0 or level > 150:
            return await message.reply("❌ Gain Range: 0-150")
        set_gain(level)
        await message.reply(f"⚡ Gain: {level}/150")
    except ValueError:
        await message.reply("❌ Only numbers! Example: /gain 30")


# ================= BASS =================
@bot.on_message(filters.command("bass"))
@owner_only
async def bass_cmd(_, message):
    try:
        if len(message.command) < 2:
            return await message.reply("Usage: /bass 0-100")
        level = int(message.command[1])
        if level < 0 or level > 100:
            return await message.reply("❌ Bass Range: 0-100")
        set_bass(level)
        await message.reply(f"🎚 Bass: {level}/100")
    except ValueError:
        await message.reply("❌ Only numbers! Example: /bass 10")


# ================= TREBLE =================
@bot.on_message(filters.command("treble"))
@owner_only
async def treble_cmd(_, message):
    try:
        if len(message.command) < 2:
            return await message.reply("Usage: /treble 0-100")
        level = int(message.command[1])
        if level < 0 or level > 100:
            return await message.reply("❌ Treble Range: 0-100")
        set_treble(level)
        await message.reply(f"✨ Treble: {level}/100")
    except ValueError:
        await message.reply("❌ Only numbers! Example: /treble 40")


# ================= VOICE MODE =================
@bot.on_message(filters.command("voice"))
@owner_only
async def voice_cmd(_, message):
    if len(message.command) < 2:
        current = get_voice_mode()
        return await message.reply(
            f"🎤 Current mode: `{current}`\n"
            "Usage: /voice female | male | normal"
        )
    mode = message.command[1].lower()
    if mode not in ["female", "male", "normal"]:
        return await message.reply("❌ Choose: female, male, normal")
    set_voice_mode(mode)
    settings = get_audio_levels()
    await message.reply(
        f"✅ Voice mode set to `{mode}`\n\n"
        f"• Volume: {settings['volume']}/400\n"
        f"• Gain: {settings['gain']}/150\n"
        f"• Bass: {settings['bass']}/100\n"
        f"• Treble: {settings['treble']}/100"
    )


# ================= STATUS =================
@bot.on_message(filters.command("status"))
@owner_only
async def status_cmd(_, message):
    settings = get_audio_levels()
    play_rooms = get_play_rooms()
    text = (
        f"🎛 **Live Status**\n"
        f"• Volume: {settings['volume']}/400\n"
        f"• Gain: {settings['gain']}/150\n"
        f"• Bass: {settings['bass']}/100\n"
        f"• Treble: {settings['treble']}/100\n"
        f"• Voice mode: `{settings.get('voice_mode','normal')}`\n"
        f"• Active VCs: {len(play_rooms)}"
    )
    if play_rooms:
        text += "\n\n📌 **VCs:**\n" + "\n".join(f"• `{cid}`" for cid in play_rooms)
    await message.reply(text)


# ================= LIST VC =================
@bot.on_message(filters.command("listvc"))
@owner_only
async def listvc_cmd(_, message):
    rooms = get_play_rooms()
    if not rooms:
        return await message.reply("❌ No active VCs.")
    text = "📋 **Active VCs:**\n\n" + "\n".join(f"• `{cid}`" for cid in rooms)
    await message.reply(text)


# ================= BROADCAST =================
@bot.on_message(filters.command("broadcast"))
@owner_only
async def broadcast_cmd(_, message: Message):
    if len(message.command) < 2:
        return await message.reply("Usage: /broadcast <message>")
    msg_text = message.text.split(maxsplit=1)[1]
    rooms = get_play_rooms()
    if not rooms:
        return await message.reply("❌ No active VCs to broadcast.")
    sent = 0
    failed = 0
    status_msg = await message.reply("🔄 Broadcasting...")
    for cid in rooms:
        try:
            await bot.send_message(cid, f"📢 **Broadcast:**\n\n{msg_text}")
            sent += 1
        except Exception as e:
            logger.warning(f"Broadcast to {cid} failed: {e}")
            failed += 1
        await asyncio.sleep(1)
    await status_msg.edit(f"✅ Done – Sent: {sent}, Failed: {failed}")


# ================= MUTE =================
@bot.on_message(filters.command("mute"))
@owner_only
async def mute_cmd(_, message):
    chat_id = get_recent_play_room()
    if not chat_id:
        rooms = get_play_rooms()
        if rooms:
            chat_id = rooms[0]
            logger.info(f"No recent play room, using first: {chat_id}")
        else:
            return await message.reply("❌ No active VC to mute.")
    room = get_room(chat_id)
    if room:
        room.force_muted = True
        room.muted = True
    ok = await bridge.mute_vc(chat_id)
    await message.reply("🔇 Muted." if ok else "❌ Mute failed.")


# ================= UNMUTE =================
@bot.on_message(filters.command("unmute"))
@owner_only
async def unmute_cmd(_, message):
    chat_id = get_recent_play_room()
    if not chat_id:
        rooms = get_play_rooms()
        if rooms:
            chat_id = rooms[0]
        else:
            return await message.reply("❌ No active VC to unmute.")
    room = get_room(chat_id)
    if room:
        room.force_muted = False
        room.muted = False
    ok = await bridge.unmute_vc(chat_id, clear_force=True)
    await message.reply("🔊 Unmuted." if ok else "❌ Unmute failed.")


# ================= AUTOMUTE =================
@bot.on_message(filters.command("automute"))
@owner_only
async def automute_cmd(_, message):
    if len(message.command) < 2:
        state = "ON" if bridge.get_automute() else "OFF"
        return await message.reply(f"⚙️ AutoMute: {state}\nUsage: /automute on/off")
    arg = message.command[1].lower()
    if arg == "on":
        bridge.set_automute(True)
        await message.reply("✅ AutoMute enabled.")
    elif arg == "off":
        bridge.set_automute(False)
        await message.reply("✅ AutoMute disabled.")
    else:
        await message.reply("❌ Use on/off.")


# ================= JOIN / RECORD =================
@bot.on_message(filters.command(["record", "join"]))
@owner_only
@handle_vc_join
async def vc_cmd(_, message):
    args = message.text.split(maxsplit=1)
    cmd = message.command[0].lower()
    try:
        if cmd == "record":
            ok = await bridge.join_record_vc()
            if ok:
                return await message.reply("✅ Recorder joined.")
            # If bridge returns False instead of raising, show the hint
            return await send_vc_join_error(message)
        if cmd == "join":
            if len(args) < 2:
                return await message.reply("Usage: /join -100xxxxxxxx")
            chat_id = int(args[1])
            ok = await bridge.join_play_vc(chat_id)
            if ok:
                await message.reply(f"✅ Joined VC: `{chat_id}`")
            else:
                # bridge returned False — likely VC not active / assistant not in group
                await send_vc_join_error(message)
    except Exception as e:
        await send_vc_join_error(message, e)


# ================= HELPER: EXTRACT CHAT ID =================
def _extract_chat_id(result):
    if hasattr(result, "id"):
        return result.id
    if hasattr(result, "chat") and hasattr(result.chat, "id"):
        return result.chat.id
    if hasattr(result, "chats") and result.chats:
        return result.chats[0].id
    raise ValueError("Cannot extract chat ID")


# ================= JOIN GROUP (ONLY JOIN, NO VC) =================
@bot.on_message(filters.command("joingroup"))
@owner_only
async def joingroup_cmd(_, message: Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        return await message.reply(
            "Usage:\n/joingroup <chat_id> | @username | t.me/joinchat/... | t.me/+..."
        )
    target = args[1].strip()
    chat_id = None
    try:
        if target.lstrip('-').isdigit():
            chat_id = int(target)
            await assistant.join_chat(chat_id)
        elif target.startswith(("https://t.me/joinchat/", "https://t.me/+", "t.me/joinchat/", "t.me/+")):
            result = await assistant.join_chat(target)
            chat_id = _extract_chat_id(result)
        else:
            username = target.lstrip('@')
            result = await assistant.join_chat(username)
            chat_id = _extract_chat_id(result)
    except Exception as e:
        return await message.reply(f"❌ Failed: {e}")
    if chat_id is None:
        return await message.reply("❌ Could not resolve.")
    await message.reply(f"✅ Joined: `{chat_id}`")


# ================= LEAVE =================
@bot.on_message(filters.command("leave"))
@owner_only
async def leave_cmd(_, message):
    await bridge.leave_record_vc()
    await bridge.leave_recent_play_vc()
    await message.reply("✅ Left VC.")


# ================= SUDO HANDLER =================
@bot.on_message(filters.command(["sudoadd", "sudodel", "sudolist"]))
async def sudo_handler(_, message):
    if not message.from_user or message.from_user.id != OWNER_ID:
        return await message.reply("⛔ Owner only.")
    cmd = message.command[0].lower()
    if cmd == "sudolist":
        sudoers = await get_sudoers()
        if not sudoers:
            return await message.reply("❌ Empty list.")
        text = "📋 Sudo list:\n" + "\n".join(f"• `{uid}`" for uid in sudoers)
        return await message.reply(text)
    uid = None
    if message.reply_to_message and message.reply_to_message.from_user:
        uid = message.reply_to_message.from_user.id
    else:
        if len(message.command) < 2:
            return await message.reply("❌ Missing user ID.")
        uid = int(message.command[1])
    if cmd == "sudoadd":
        await add_sudoer(uid)
        await message.reply(f"✅ Added sudo: `{uid}`")
    elif cmd == "sudodel":
        await del_sudoer(uid)
        await message.reply(f"❌ Removed sudo: `{uid}`")

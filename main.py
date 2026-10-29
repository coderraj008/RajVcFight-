import asyncio
import signal
import sys
import logging

from pytgcalls import idle

import bridge  # noqa
import commands  # noqa

from clients import (
    assistant,
    bot,
    call,
)

from db import get_startup_state
from pyrogram.errors import FloodWait

logger = logging.getLogger(__name__)

# ================= SIGNAL =================
def handler(sig, frame):
    print("Graceful shutdown...")
    sys.exit(0)

signal.signal(signal.SIGINT, handler)
signal.signal(signal.SIGTERM, handler)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logging.getLogger("pyrogram").setLevel(logging.ERROR)
logging.getLogger("pymongo").setLevel(logging.ERROR)

loop = asyncio.get_event_loop()

# ================= RETRY HELPER =================
async def start_with_retry(client, name="Client", max_attempts=10):
    attempt = 0
    while attempt < max_attempts:
        try:
            await client.start()
            logger.info(f"{name} started successfully.")
            return True
        except FloodWait as e:
            wait = e.value
            logger.warning(f"{name} flood‑wait: {wait}s. Waiting before retry...")
            await asyncio.sleep(wait)
            attempt += 1
        except Exception as e:
            logger.error(f"{name} start error: {e}")
            await asyncio.sleep(5)
            attempt += 1
    logger.error(f"Failed to start {name} after {max_attempts} attempts.")
    return False

# ================= MAIN =================
async def main():
    logger.info("Starting...")
    bridge.assert_media_runtime_dependencies()

    # Start clients with retry logic
    bot_ok = await start_with_retry(bot, "Bot")
    if not bot_ok:
        logger.critical("Bot failed to start. Exiting.")
        sys.exit(1)

    assistant_ok = await start_with_retry(assistant, "Assistant")
    if not assistant_ok:
        logger.critical("Assistant failed to start. Exiting.")
        sys.exit(1)

    # Start pytgcalls
    try:
        await call.start()
        logger.info("PyTgCalls started.")
    except Exception as e:
        logger.error(f"PyTgCalls start error: {e}")
        sys.exit(1)

    # Start mute watchdog (enforces force_muted)
    asyncio.create_task(bridge.mute_watchdog())
    logger.info("Mute watchdog started.")

    # Start silence watchdog (auto-mute on silence)
    asyncio.create_task(bridge.silence_watchdog())
    logger.info("Silence watchdog started.")

    # Load state
    try:
        state = await get_startup_state() or {}
    except Exception as e:
        logger.warning("DB state load failed: %s", e)
        state = {}

    # Auto‑join recorder
    if state.get("recorder_joined"):
        try:
            await bridge.join_record_vc()
            logger.info("Auto joined recorder VC")
        except Exception as exc:
            logger.warning("Recorder join failed: %s", exc)

    # Auto‑join control VC
    control_vc = state.get("control_vc")
    if control_vc is not None:
        try:
            await bridge.join_play_vc(control_vc)
            logger.info("Auto joined control VC %s", control_vc)
        except Exception as exc:
            logger.warning("Control VC join failed: %s", exc)

    logger.info("Bot ready ✅")
    await idle()

    # Clean shutdown
    await bot.stop()
    await assistant.stop()

if __name__ == "__main__":
    loop.run_until_complete(main())

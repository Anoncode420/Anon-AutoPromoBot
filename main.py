import asyncio
import pyroaddon
import random
import tgcrypto

from pyrogram import Client, filters, idle
from pyrogram.types import (
    Dialog,
    Message,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from pyrogram.enums import ChatType
from pyrogram.errors import (
    SessionPasswordNeeded,
    PeerFlood,
    InviteHashInvalid,
    ChatWriteForbidden,
    UserBannedInChannel,
    ChatAdminRequired,
    ChatInvalid,
    ChannelPrivate,
)

from pymongo import MongoClient

# ----- Config ---- #

API_ID = 4277083
API_HASH = "bb0ddae0921fc020ce61faae2d1261d5"
BOT_TOKEN = "7862024785:AAEYtO3CW5N_kLvn5b5RvK7G1zeyTlCOCII"
DB_URI = "mongodb+srv://OTPBot:OTPBot@otpbot.tf42f.mongodb.net/?retryWrites=true&w=majority&appName=OTPBot"
PROMOTION_CHANNEL = -1002310923659
AUTO_PROMOTION_INTERVAL = 3600
AUTH_USERS = [5294360309, 6725223313]

bot = Client(
    "Auto Promotion Bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

client_list: list[Client] = []

start_message = """
**Auto Promotion Bot**

Avaible Commands;

 - `/save` > while replying forwarded post.
 - `/delete` (post id) ; to delete post.
 - `/list` (`posts` OR `clients`) ; to get list of posts OR clients.
 - `/new` ; to add new client.
 - `/remove` (user id) ; to remove client.
"""

# ----- Database ----- #

db_client = MongoClient(DB_URI)
database = db_client["auto_promotion"]

# ---- ---- #

def add_session(user_id: int, session: str) -> None:
    database.sessions.insert_one(
        {
            "user_id": user_id,
            "session": session
        }
    )

def remove_session(user_id: int) -> None:
    database.sessions.delete_one(
        {"user_id": user_id}
    )

def is_session(user_id: int) -> bool:
    return bool(database.sessions.find_one({"user_id": user_id}))

def get_all_sessions() -> list[dict]:
    return [data for data in database.sessions.find({})]

# ---- ---- #

def add_post(message_id: int) -> None:
    database.posts.insert_one({"message_id": message_id,})

def remove_post(message_id: int) -> None:
    database.posts.delete_one({"message_id": message_id})

def is_post(message_id: int) -> bool:
    return bool(database.posts.find_one({"message_id": message_id}))

def get_all_posts() -> list[int]:
    return [data["message_id"] for data in database.posts.find({})]

# ---- ---- #

def add_group(username: str) -> None:
    database.groups.insert_one(
        {"username": username}
    )

def is_group(username: str) -> bool:
    return bool(database.groups.find_one({"username": username}))

def get_all_groups() -> list[str]:
    return [data['username'] for data in database.groups.find({})]

def remove_chat(username: str) -> None:
    database.groups.delete_one(
        {"username": username}
    )

# ----- Functions ----- #

async def setup_clients() -> None:
    sessions = get_all_sessions()
    if len(sessions) > 0:
        for session in sessions:
            promo_client = Client(
                f"Auto Promo #{session['user_id']}",
                api_id=API_ID,
                api_hash=API_HASH,
                session_string=str(session['session']).strip()
            )
            try:
                await promo_client.start()
                print(f"Promo Client: {promo_client.me.first_name} Started!")
                client_list.append(promo_client)
            except:
                print(f"Cannot start {session['user_id']}, removing.....")
                remove_session(session["user_id"])
                print("Removed!")
        print("All sessions loaded!")
    else:
        print("NO Sessions!")

async def join_promotion_channel():
    try:
        join_link = await bot.export_chat_invite_link(PROMOTION_CHANNEL)

        for cli in client_list:
            try:
                await cli.join_chat(join_link)
            except:
                pass

    except:
        pass

async def join_random_chat(client: Client) -> None:
    all_chats = get_all_groups()
    random_chat = random.choice(all_chats)
    try:
        await client.join_chat(random_chat)
        print(f"client {client.me.id} Successfully joined the chat: @{random_chat}")

    except PeerFlood:
        print("Error: Too many join requests. Please try again later.")

    except UserBannedInChannel:
        print("Error: The bot or user is banned from this chat.")
        return await join_random_chat(client)

    except (InviteHashInvalid, ChatWriteForbidden, ChatAdminRequired, ChannelPrivate, ChatInvalid):
        print("Error: The chat ID or username is invalid.")
        remove_chat(random_chat)
        return await join_random_chat(client)

    except Exception as e:
        print(f"An unexpected error occurred: {e}")

async def send_promotion(client: Client, msg_ids: list[int]):
    async for dialog in client.get_dialogs():
        dialog: Dialog
        if dialog.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
            try:
                await (
                    await client.get_messages(
                        PROMOTION_CHANNEL, random.choice(msg_ids)
                    )
                ).forward(dialog.chat.id)
                #print(f"{client.me.first_name}: {dialog.chat.title}: Sent Promotion Message!")
            except: #Exception as e:
                pass
                #print(f"{client.me.first_name}: {dialog.chat.title}: AutoPromoErr - {e}")
        await asyncio.sleep(1)
    await join_random_chat(client)

# ----- Handlers ----- #

@bot.on_message(filters.command("start") & filters.private & filters.user(AUTH_USERS))
async def start(_, message: Message):
    await message.reply(start_message)

@bot.on_message(filters.command("save") & filters.private & filters.user(AUTH_USERS))
async def save(_, message: Message):
    replied = message.reply_to_message
    if replied and (replied.forward_from_chat or replied.forward_from):
        post = await replied.forward(PROMOTION_CHANNEL)
        add_post(post.id)
        await message.reply(
            f"Message saved for auto promotion. \n\n**Message ID:** {post.id}",
            reply_markup=InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("🙈 View", url=f"{post.link}")]
                ]
            ),
        )
    else:
        await message.reply("Please forward post here and type /save while replying that post")

@bot.on_message(filters.command("delete") & filters.private & filters.user(AUTH_USERS))
async def delete(_, message: Message):
    if len(message.command) != 2:
        return await message.reply("Please share message id of the post to delete the post.")

    try:
        post_id = int(message.command[1])
    except:
        return await message.reply("Please share message id of the post to delete the post.")

    if not is_post(post_id):
        return await message.reply("Invalid post id.")

    remove_post(post_id)
    try:
        await bot.delete_messages(PROMOTION_CHANNEL, post_id)
    except:
        pass
    await message.reply(f"Removed {post_id} from db")

@bot.on_message(filters.command("list") & filters.private & filters.user(AUTH_USERS))
async def list(_, message: Message):
    if len(message.command) != 2:
        return await message.reply("Please share list task; `posts` OR `clients`")

    list_task = str(message.command[1])
    wait = await message.reply("Loading.....")

    if list_task.lower() in ["post", "posts"]:
        list_message = "**Posts Messages list!** \n\n"
        channel_id = int(str(PROMOTION_CHANNEL).replace("-100", ""))
        all_posts = get_all_posts()
        if len(all_posts) == 0:
            return await wait.edit("**0 Posts**")
        for post_id in all_posts:
            list_message += f" - `{post_id}`:  [view post](https://t.me/c/{channel_id}/{post_id}) \n"
        list_message += f"\n**Total {len(all_posts)} Posts**"
    else:
        list_message = "**Promotion Clients list!** \n\n"
        if len(client_list) == 0:
            return await wait.edit("**0 Clients**")
        for client in client_list:
            list_message += f" - `{client.me.id}`: {client.me.mention} \n"
        list_message += f"\n**Total {len(client_list)} Clients**"

    try:
        await wait.edit(list_message, disable_web_page_preview=True)
    except:
        await wait.reply(list_message, disable_web_page_preview=True)
        await wait.delete()

@bot.on_message(filters.command("new") & filters.private & filters.user(AUTH_USERS))
async def add_client(_, message: Message):
    await message.reply_text("**Okay!** Let's Setup a new session",)

    phone_number: Message = await bot.ask(
        message.chat.id,
        "**1.** Enter your 𝗍𝖾𝗅𝖾𝗀𝗋𝖺𝗆 account phone 𝗇𝗎𝗆𝖻𝖾𝗋 to add the session: \n\n__send /cancel to cancel the operation.__",
        filters=filters.text,
        timeout=120,
    )

    if phone_number.text.startswith("/"):
        return await message.reply_text("**Cancelled!**")

    elif not phone_number.text.startswith("+") and not str(phone_number.text[1:]).isdigit():
        return await message.reply_text(
            "**Error!** Phone 𝗇𝗎𝗆𝖻𝖾𝗋 𝗆𝗎𝗌𝗍 be in digits & should contain country code."
        )

    try:
        client = Client(
            name="Promo-Client",
            api_id=API_ID,
            api_hash=API_HASH,
            in_memory=True,
        )
        await client.connect()

        code = await client.send_code(phone_number.text)
        ask_otp: Message = await bot.ask(
            message.chat.id,
            "**2.** Enter the OTP sent to your 𝗍𝖾𝗅𝖾𝗀𝗋𝖺𝗆 account by seprating ebery 𝗇𝗎𝗆𝖻𝖾𝗋 with a space. \n\n**𝖤𝗑𝖺𝗆𝗉𝗅𝖾:** `2 4 1 7 4`\n\n__Send /cancel to cancel the operation.__",
            filters=filters.text,
            timeout=300,
        )
        if ask_otp.text.startswith("/"):
            return await message.reply_text("**Cancelled!**")

        otp = ask_otp.text.replace(" ", "")

        try:
            await client.sign_in(phone_number.text, code.phone_code_hash, otp)
        except SessionPasswordNeeded:
            two_step_pass: Message = await bot.ask(
                message.chat.id,
                "**3.** Enter your two step verification password: \n\n__Send /cancel to cancel the operation.__",
                filters=filters.text,
                timeout=120,
            )
            if two_step_pass.text.startswith("/"):
                return await message.reply_text("**Cancelled!**")

            await client.check_password(two_step_pass.text)

        session_string = await client.export_session_string()
        await message.reply_text(
            f"**Success!** Your session string is generate. Adding it to database..."
        )
        await client.disconnect()
        msg = await message.reply_text("Starting the client...")
        try:
            client = Client(
                f"Auto Promo {phone_number.text}",
                API_ID,
                API_HASH,
                session_string=session_string,
            )
            await client.start()
            add_session(client.me.id, session_string)
            client_list.append(client)
            try:
                join_link = await bot.export_chat_invite_link(PROMOTION_CHANNEL)
                await client.join_chat(join_link)
            except Exception as e:
                print(f"JoinPromotionChannelErr: {e}")
            await msg.edit_text(f"✅ **{client.me.mention}: Client started successfully.**",)
        except Exception as e:
            await msg.edit_text(f"**Error!** {e}")

    except TimeoutError:
        await message.reply_text("**TimeOutError!** YOu took longer than expected to 𝖼𝗈𝗆𝗉𝗅𝖾𝗍𝖾 the process. Please try again.")

    except Exception as e:
        await message.reply_text(f"**Error!** {e}")

@bot.on_message(filters.command("remove") & filters.private & filters.user(AUTH_USERS))
async def remove_client(_, message: Message):
    if len(message.command) != 2:
        return await message.reply("Please share user id of the telegram account to delete the client.")

    try:
        user_id = int(message.command[1])
    except:
        return await message.reply("Please share user id of the telegram account to delete the client.")

    if not is_session(user_id):
        return await message.reply("Invalid client user id.")

    wait = await message.reply("removing....")
    remove_session(user_id)
    for client in client_list:
        if client.me.id == user_id:
            client_list.remove(client)
            break
    await wait.reply(f"**Removed** {user_id} from auto promotion!")

@bot.on_message(filters.command("addgroups") & filters.private & filters.user(AUTH_USERS))
async def add_grpups(_, message: Message):
    args: str = "".join(message.text.split(maxsplit=1)[1:]).split(" ", 0)
    if len(args) == 0:
        return await message.reply("Please provide group list space by space")

    if " " in args:
        group_list = args.split(" ")
    else:
        group_list = [args]

    wait = await message.reply(f"Adding {len(group_list)} in DB")

    for group_username in group_list:
        if "@" in group_username:
            group_username = group_username.replace("@", "")

        elif "https://t.me/" in group_username:
            group_username = str(group_username.split("/")[3])

        add_group(group_username)

    await wait.edit(f"Added All groups in {len(group_list)} in DB, now we have total {len(get_all_groups())} groups in Database.")

# ----- Main ---- #

# run auto promotion in a separate thread
async def auto_promotion():
    msg_ids = get_all_posts()
    if msg_ids:
        tasks = [send_promotion(client, msg_ids) for client in client_list]
        await asyncio.gather(*tasks)
        await asyncio.sleep(AUTO_PROMOTION_INTERVAL)
        await auto_promotion()


async def main():
    # boot the bot and setup clients and users
    await bot.start()
    await setup_clients()
    await join_promotion_channel()

    # run auto promotion in a separate thread as daemon process
    # Thread(target=auto_promotion, daemon=True).start()

    print(f"Bot started as @{bot.me.username}!")
    try:
        await bot.send_message(PROMOTION_CHANNEL, "**Bot Started!**")
    except:
        pass
    await auto_promotion()

    await idle()

    print(f"Bot stopped!")
    await bot.stop()
    # lmao ded

if __name__ == "__main__":
    bot.run(main())

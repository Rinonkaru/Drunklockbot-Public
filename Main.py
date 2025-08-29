# -------------------------------------------------------------------
# License Information
# -------------------------------------------------------------------

"""
Drunklockbot - A Twitch Chat Bot for some economy functions and more!
Copyright (C) 2025 Rinonkaru

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, version 3 of the License.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

# -------------------------------------------------------------------
# Imports
# -------------------------------------------------------------------

import os
import json
import random
import asyncio

from pickledb import PickleDB
from twitchAPI.helper import first
from twitchAPI.twitch import Twitch
from twitchAPI.type import AuthScope
from twitchAPI.chat import Chat, ChatCommand
from twitchAPI.oauth import UserAuthenticationStorageHelper
from twitchAPI.chat.middleware import ChannelUserCommandCooldown, UserRestriction

# -------------------------------------------------------------------
# Constant Variables
# -------------------------------------------------------------------

BOT_ID = None
OWNER_ID = None
TARGET_ID = None
TARGET_CHANNELS = ["Drunklockholmes"]
CLIENT_ID = None
CLIENT_SECRET = None
SCOPE = [
	AuthScope.CHANNEL_BOT,
	AuthScope.CHAT_READ,
	AuthScope.CHAT_EDIT,
	AuthScope.CHANNEL_MODERATE,
	AuthScope.MODERATION_READ,
	AuthScope.MODERATOR_READ_CHAT_MESSAGES,
	AuthScope.MODERATOR_READ_CHATTERS
]

# -------------------------------------------------------------------
# Global Variables
# -------------------------------------------------------------------

currency = None
chat: Chat = None
data: PickleDB = None
twitch: Twitch = None

# -------------------------------------------------------------------
# Helper Functions
# -------------------------------------------------------------------

def extract_mention(text: str):
	if text.find("@") == -1:
		return text
	start = text.find("@")
	position = start + 1
	while position < len(text):
		if text[position] == " ":
			return text[start + 1:position]
		position += 1
	return text[start + 1:]

async def ensure_twitch_user_exists(username: str) -> bool:
	user = await first(twitch.get_users(logins = [username]))
	if user: return True
	return False

def ensure_user_exists(mention: bool = False, executor_return: bool = False, target_return: bool = False):
	def decorator(function):
		async def wrapper(command: ChatCommand):
			executor = command.user.name.lower()
			if executor not in data.all():
				data.set(executor, (0, 500))
			target = None
			if mention and command.parameter.find("@") != -1:
				target = extract_mention(command.parameter).lower()
				if target not in data.all():
					data.set(target, (0, 500))
			if executor_return and target_return:
				await function(command, executor, target)
			elif executor_return and not target_return:
				await function(command, executor)
			elif target_return and not executor_return:
				await function(command, target)
			else:
				await function(command)
		return wrapper
	return decorator

# -------------------------------------------------------------------
# Events / Blocked Command Handlers
# -------------------------------------------------------------------

async def default_blocked_command_handler(command: ChatCommand):
	await command.reply("For one reason or another, command execution was blocked")
	return

async def cooldown_blocked_command_handler(command: ChatCommand):
	await command.reply("Command is on cooldown! You'll have to wait!")
	return
	
# -------------------------------------------------------------------
# Streamer Only Commands
# -------------------------------------------------------------------

async def set_currency(command: ChatCommand):
	if len(command.parameter) == 0:
		await command.reply("You have to specify a new currency name.")
		return
	data.set("currency", command.parameter)
	await command.reply("Currency name is set to: " + command.parameter)

@ensure_user_exists(True, False, True)
async def set_wallet(command: ChatCommand, target: str):
	if len(command.parameter) == 0:
		await command.reply("You have to provide a user and an amount to set their wallet to.")
		return
	if not await ensure_twitch_user_exists(target.lower()):
		await command.reply("The specified user does not exist on Twitch.")
		return
	parameters = command.parameter.lower().split(" ")
	amount = int(parameters[1])
	wallet, bank = data.get(target)
	wallet = amount
	data.set(target, (wallet, bank))
	await command.reply(f"{target.capitalize()}'s wallet has been set to: {wallet} {currency}.")

@ensure_user_exists(True, False, True)
async def set_bank(command: ChatCommand, target: str = None):
	if len(command.parameter) == 0:
		await command.reply("You have to provide a user and an amount to set their bank to.")
		return
	if not await ensure_twitch_user_exists(target.lower()):
		await command.reply("The specified user does not exist on Twitch.")
		return
	parameters = command.parameter.lower().split(" ")
	amount = int(parameters[1])
	wallet, bank = data.get(target)
	bank = amount
	data.set(target, (wallet, bank))
	await command.reply(f"{target.capitalize()}'s bank has been set to: {bank} {currency}.")

# -------------------------------------------------------------------
# USER COMMANDS
# -------------------------------------------------------------------

@ensure_user_exists(False, True, False)
async def work(command: ChatCommand, executor: str):
	wallet, bank = data.get(executor)
	earnings = random.randint(1, 100)
	data.set(executor, (wallet + earnings, bank))
	await command.reply(f"You worked and earned {earnings} {currency}.")

@ensure_user_exists(True, True, True)
async def balance(command: ChatCommand, executor: str, target: str = None):
	if len(command.parameter) == 0:
		wallet, bank = data.get(executor)
		await command.reply(f"Wallet: {wallet} {currency} | Bank: {bank} {currency}")
		return
	if not await ensure_twitch_user_exists(target.lower()):
		await command.reply("The specified user does not exist on Twitch.")
		return
	wallet, bank = data.get(target)
	await command.reply(f"Wallet: {wallet} {currency} | Bank: {bank} {currency}")

@ensure_user_exists(False, True, False)
async def deposit(command: ChatCommand, executor: str):
	if len(command.parameter) == 0:
		await command.reply("You have to provide an amount to deposit.")
		return
	if not command.parameter.isdigit():
		await command.reply("Please provide a valid number to deposit.")
		return
	amount = abs(int(command.parameter))
	wallet, bank = data.get(executor)
	if wallet < amount:
		await command.reply(f"You cannot deposit {amount} {currency}, you only have {wallet} {currency} in your wallet.")
		return
	data.set(executor, (wallet - amount, bank + amount))
	await command.reply(f"You have deposited {amount} {currency} into your bank account.")

@ensure_user_exists(False, True, False)
async def withdraw(command: ChatCommand, executor: str):
	if len(command.parameter) == 0:
		await command.reply("You have to provide an amount to withdraw.")
		return
	if not command.parameter.isdigit():
		await command.reply("Please provide a valid number to withdraw.")
		return
	amount = abs(int(command.parameter))
	wallet, bank = data.get(executor)
	if bank < amount:
		await command.reply(f"You cannot withdraw {amount} {currency}, you only have {bank} {currency} in your bank.")
		return
	data.set(executor, (wallet + amount, bank - amount))
	await command.reply(f"You have withdrawn {amount} {currency} into your wallet.")

@ensure_user_exists(False, True, False)
async def gamble(command: ChatCommand, executor: str):
	if len(command.parameter) == 0:
		await command.reply("You have to provide an amount to gamble.")
		return
	if not command.parameter.isdigit():
		await command.reply("Please provide a valid number to gamble.")
		return
	amount = abs(int(command.parameter))
	wallet, bank = data.get(executor)
	if wallet < amount:
		await command.reply(f"You don't have enough {currency} to gamble the amount you wanted.")
		return
	fate = random.choices(["fail", "success", "lucky"], [0.5, 0.48, 0.02])[0]
	if fate == "fail":
		data.set(executor, (wallet - amount, bank))
		await command.reply(f"You lost {amount} {currency}!")
	elif fate == "success":
		data.set(executor, (wallet + amount, bank))
		await command.reply(f"You won {amount * 2} {currency}!")
	elif fate == "lucky":
		data.set(executor, (wallet + amount * 3, bank))
		await command.reply(f"You won {amount * 4} {currency}!")

@ensure_user_exists(True, True, True)
async def transfer(command: ChatCommand, executor: str, target: str):
	if len(command.parameter) == 0:
		await command.reply("You have to specify a user and an amount to transfer.")
		return
	parameters = command.parameter.split(" ")
	if len(parameters) != 2:
		await command.reply("You have to specify an amount and the user you're transferring to.")
		return
	if not parameters[0].isdigit():
		await command.reply("You have to specify a valid integer amount to transfer.")
		return
	if parameters[1].find("@") == -1:
		await command.reply("You have to provide a valid mentioned user to transfer to.")
		return
	if not await ensure_twitch_user_exists(target.lower()):
		await command.reply("The specified user does not exist on Twitch.")
		return
	amount = abs(int(parameters[0]))
	executor_wallet, executor_bank = data.get(executor)
	target_wallet, target_bank = data.get(target)
	if executor_wallet < amount:
		await command.reply("You don't have enough {0} to transfer.".format(currency))
		return
	data.set(executor, (executor_wallet - amount, executor_bank))
	data.set(target, (target_wallet + amount, target_bank))
	await command.reply(f"{executor.capitalize()} transferred {amount} {currency} to {target.capitalize()}!")

@ensure_user_exists(True, True, True)
async def rob(command: ChatCommand, executor: str, target: str = None):
	if len(command.parameter) == 0:
		await command.reply("You have to provide an amount to rob.")
		return
	if command.parameter.lower().find("@") == -1:
		await command.reply("You have to specify a user to try and rob.")
		return
	if not await ensure_twitch_user_exists(target.lower()):
		await command.reply("The specified user does not exist on Twitch.")
		return
	executor_wallet, executor_bank = data.get(executor)
	target_wallet, target_bank = data.get(target)
	if target == executor:
		await command.reply("Robbing yourself? Really? Get some help...")
		return
	if target == "drunklockbot":
		await command.reply("Skill issue...I'm sorry, it's fatal.")
		return
	if target_wallet == 0:
		await command.reply(f"You cannot rob {target.capitalize()} because they have no money!")
		return
	fate = random.choices(["fail", "success", "lucky"], [0.5, 0.48, 0.02])[0]
	if fate == "fail":
		loss = random.randint(0, 100) if executor_wallet >= 100 else random.randint(0, executor_wallet)
		data.set(executor, (executor_wallet - loss, executor_bank))
		await command.reply(f"You lost {loss} {currency} while trying to rob {target.capitalize()}!")
		return
	elif fate == "success":
		amount = random.randint(1, 100) if target_wallet >= 100 else random.randint(0, target_wallet)
		data.set(target, (target_wallet - amount, target_bank))
		data.set(executor, (executor_wallet + amount, executor_bank))
		await command.reply(f"You succeeded and got {amount} {currency}!")
		return
	elif fate == "lucky":
		amount = random.randint(1, target_wallet)
		data.set(target, (target_wallet - amount, target_bank))
		data.set(executor, (executor_wallet + amount, executor_bank))
		await command.reply(f"You got lucky and got {amount} {currency}!")
		return
		
# -------------------------------------------------------------------
# Main
# -------------------------------------------------------------------

async def run():
	global twitch, chat, data, currency
	
	twitch = await Twitch(CLIENT_ID, CLIENT_SECRET)
	helper = UserAuthenticationStorageHelper(twitch, SCOPE)
	await helper.bind()
	
	chat = await Chat(twitch)
	chat.set_prefix(">")
	
	chat.register_command("currency", set_currency, command_middleware = [UserRestriction(allowed_users = ["drunklockholmes", "rinonkaru"])])
	chat.register_command("set_wallet", set_wallet, command_middleware = [UserRestriction(allowed_users = ["drunklockholmes", "rinonkaru"])])
	chat.register_command("set_bank", set_bank, command_middleware = [UserRestriction(allowed_users = ["drunklockholmes", "rinonkaru"])])
	
	chat.register_command("balance", balance)
	chat.register_command("deposit", deposit)
	chat.register_command("withdraw", withdraw)
	chat.register_command("gamble", gamble)
	chat.register_command("transfer", transfer)
	
	chat.register_command("work", work, command_middleware = [ChannelUserCommandCooldown(60, execute_blocked_handler = cooldown_blocked_command_handler)])
	chat.register_command("rob", rob, command_middleware = [ChannelUserCommandCooldown(60, execute_blocked_handler = cooldown_blocked_command_handler)])
	
	chat.default_command_execution_blocked_handler = default_blocked_command_handler
	
	chat.start()
	
	if not os.path.exists("storage.json"):
		f = open("storage.json", "w")
		json.dump({"currency": "BrainCells", "default_user": [0, 500]}, f)
		f.close()
	data = PickleDB("storage.json")
	
	try:
		await chat.join_room(TARGET_CHANNELS[0])
		await chat.send_message(TARGET_CHANNELS[0], "Drunklockbot is now online!")
		currency = data.get("currency") if data.get("currency") is not None else "BrainCells"
		input("Bot is running. Press ENTER to stop...\n")
	finally:
		await chat.send_message(TARGET_CHANNELS,"Drunklockbot is going offline. Bye!")
		data.save()
		chat.stop()
		await twitch.close()
		
if __name__ == "__main__":
	asyncio.run(run())





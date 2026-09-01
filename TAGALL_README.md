# TagAll final fix

`/tagall Hello ❤️` sends `Hello ❤️` together with all member mentions that
the bot has stored.

The previous "not enough members" gate is removed, as are artificial small
member cutoffs.

Telegram Bot API limitation: a normal bot cannot enumerate the complete
historical membership of a group. The bot must have observed/stored a user's
ID before it can create a direct `tg://user?id=...` mention.

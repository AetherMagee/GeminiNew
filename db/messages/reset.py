from typing import Union

from asyncpg import UndefinedTableError

import db.shared as dbs
import db.table_creator


# noinspection SqlWithoutWhere
async def mark_all_messages_as_deleted(chat_id: int):
    async with dbs.pool.acquire() as conn:
        san_chat_id = await dbs.sanitize_chat_id(chat_id)
        try:
            await conn.execute(f"UPDATE messages{san_chat_id} SET deleted=true")
        except UndefinedTableError:
            await db.table_creator.create_message_table(conn, san_chat_id)
            pass


async def attempt_delete_message(chat_id: int, target: int) -> bool:
    async with dbs.pool.acquire() as conn:
        san_chat_id = await dbs.sanitize_chat_id(chat_id)
        try:
            result = await conn.execute(f"UPDATE messages{san_chat_id} SET deleted=false WHERE message_id=$1", target)
            if str(result).split(" ")[1] == "1":
                return True
            else:
                return False
        except UndefinedTableError:
            await db.table_creator.create_message_table(conn, san_chat_id)
            return True


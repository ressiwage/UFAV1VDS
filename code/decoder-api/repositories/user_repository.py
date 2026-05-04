import secrets
import mysql.connector
from fastapi import HTTPException
from core.security import hash_password, generate_token


class UserRepository:
    def __init__(self, conn):
        self.conn = conn

    def create(self, username: str, password: str) -> None:
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO users (username, password) VALUES (%s, %s)",
                (username, hash_password(password)),
            )
            self.conn.commit()
        except mysql.connector.IntegrityError:
            raise HTTPException(status_code=400, detail="User exists")
        finally:
            cursor.close()

    def get_by_credentials(self, username: str, password: str) -> dict | None:
        cursor = self.conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT id FROM users WHERE username = %s AND password = %s",
            (username, hash_password(password)),
        )
        result = cursor.fetchone()
        cursor.close()
        return result

    def set_token(self, user_id: int) -> str:
        token = generate_token()
        cursor = self.conn.cursor()
        cursor.execute("UPDATE users SET token = %s WHERE id = %s", (token, user_id))
        self.conn.commit()
        cursor.close()
        return token

    def get_by_token(self, token: str) -> dict | None:
        cursor = self.conn.cursor(dictionary=True)
        cursor.execute("SELECT id, username FROM users WHERE token = %s", (token,))
        user = cursor.fetchone()
        cursor.close()
        return user
import os
import json
from dotenv import load_dotenv
from openai import OpenAI
import mysql.connector

load_dotenv()


class EmbeddingEngine:

    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        self.db = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="enterprise_core"
        )

    def generate_embedding(self, text: str):

        response = self.client.embeddings.create(
            model="text-embedding-3-small",
            input=text
        )

        return response.data[0].embedding

    def embed_chunk(self, chunk_id: int):

        cursor = self.db.cursor(dictionary=True)

        cursor.execute(
            "SELECT content FROM knowledge_chunks WHERE id = %s",
            (chunk_id,)
        )

        chunk = cursor.fetchone()

        if not chunk:
            return "Chunk not found"

        embedding = self.generate_embedding(chunk["content"])

        cursor.execute(
            """
            INSERT INTO knowledge_embeddings (chunk_id, embedding)
            VALUES (%s, %s)
            """,
            (chunk_id, json.dumps(embedding))
        )

        self.db.commit()

        return "Embedding stored successfully"

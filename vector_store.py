# vector_store.py

"""
This module handles the vectorization of text data and storage
into a ChromaDB collection.
"""

import chromadb
from sentence_transformers import SentenceTransformer
import config
import json

class VectorStore:
    """
    Manages the creation of embeddings and storage in ChromaDB.
    """

    def __init__(self):
        """
        Initializes the ChromaDB client, the embedding model, and the collection.
        """
        print("Initializing Vector Store...")
        self.embedding_model = SentenceTransformer(config.EMBEDDING_MODEL_NAME)
        self.chroma_client = chromadb.PersistentClient(path=config.CHROMA_DB_PATH)
        self.collection = self.chroma_client.get_or_create_collection(
            name=config.CHROMA_COLLECTION_NAME
        )
        print("Vector Store initialized successfully.")

    def add_startup_data(self, startup_info):
        """
        Creates an embedding for the startup's information and adds it to ChromaDB.

        Args:
            startup_info (dict): A dictionary containing startup details including 'app_details'.
        """
        try:
            company_name = startup_info['name']
            
            # Combine profile description and app descriptions for a rich embedding document.
            document_content = startup_info.get('profile_description', '')
            app_details = startup_info.get('app_details', [])
            
            if app_details:
                for app in app_details:
                    document_content += f"\n\n--- App: {app.get('title', 'N/A')} ---\n{app.get('description', '')}"

            # Generate a unique ID for the document.
            doc_id = company_name.replace(' ', '-').lower()

            # Create the embedding.
            embedding = self.embedding_model.encode(document_content).tolist()

            # Prepare metadata. Store detailed app info as a JSON string.
            metadata = {
                "name": company_name,
                "website": startup_info.get('website', ''),
                "industry": startup_info.get('industry', ''),
                "has_app": "Yes" if app_details else "No",
                "app_details_json": json.dumps(app_details) if app_details else "[]"
            }

            # Add the data to the collection.
            self.collection.add(
                ids=[doc_id],
                embeddings=[embedding],
                documents=[document_content],
                metadatas=[metadata]
            )
            print(f"  -> Successfully vectorized and stored '{company_name}'. Has App: {metadata['has_app']}")

        except Exception as e:
            print(f"❌ Error processing and storing '{startup_info.get('name', 'Unknown')}': {e}")

import time
from .BaseController import BaseController
from models.db_schemes import Project, DataChunk
from stores.llm.LLMEnums import DocumentTypeEnum
from typing import List
import json

class NLPController(BaseController):

    def __init__(self, vectordb_client, generation_client, 
                 embedding_client, template_parser):
        super().__init__()

        self.vectordb_client = vectordb_client
        self.generation_client = generation_client
        self.embedding_client = embedding_client
        self.template_parser = template_parser

    def create_collection_name(self, project_id: str):
        return f"collection_{project_id}".strip()
    
    def reset_vector_db_collection(self, project: Project):
        collection_name = self.create_collection_name(project_id=project.project_id)
        return self.vectordb_client.delete_collection(collection_name=collection_name)
    
    def get_vector_db_collection_info(self, project: Project):
        collection_name = self.create_collection_name(project_id=project.project_id)
        collection_info = self.vectordb_client.get_collection_info(collection_name=collection_name)

        return json.loads(
            json.dumps(collection_info, default=lambda x: x.__dict__)
        )
    
    def index_into_vector_db(self, project: Project, chunks: List[DataChunk],
                                   chunks_ids: List[int], 
                                   do_reset: bool = False):
        
        # step1: get collection name
        collection_name = self.create_collection_name(project_id=project.project_id)

        # step2: manage items
        texts = [ c.chunk_text for c in chunks ]
        metadata = [ c.chunk_metadata for c in  chunks]
        # vectors = [
        #     self.embedding_client.embed_text(text=text, 
        #                                      document_type=DocumentTypeEnum.DOCUMENT.value)
        #     for text in texts
        # ]
        vectors = self.embedding_client.embed_text(texts=texts, 
                                              document_type=DocumentTypeEnum.DOCUMENT.value)
        # step3: create collection if not exists
        _ = self.vectordb_client.create_collection(
            collection_name=collection_name,
            embedding_size=self.embedding_client.embedding_size,
            do_reset=do_reset,
        )

        # step4: insert into vector db
        _ = self.vectordb_client.insert_many(
            collection_name=collection_name,
            texts=texts,
            metadata=metadata,
            vectors=vectors,
            record_ids=chunks_ids,
        )

        return True

    def search_vector_db_collection(self, project: Project, text: str, limit: int = 10):

        # step1: get collection name
        collection_name = self.create_collection_name(project_id=project.project_id)

        # step2: get text embedding vector
        vector = self.embedding_client.embed_text(texts=[text], 
                                                 document_type=DocumentTypeEnum.QUERY.value)[0]

        if not vector or len(vector) == 0:
            return False

        # step3: do semantic search
        results = self.vectordb_client.search_by_vector(
            collection_name=collection_name,
            vector=vector,
            limit=limit
        )

        if not results:
            return False

        return results
    
    def answer_rag_question(self, project: Project, query: str, limit: int = 10):
        
        answer, full_prompt, chat_history = None, None, None

        # step1: retrieve related documents
        retrieved_documents = self.search_vector_db_collection(
            project=project,
            text=query,
            limit=limit,
        )

        if not retrieved_documents or len(retrieved_documents) == 0:
            return answer, full_prompt, chat_history
        
        # step2: Construct LLM prompt
        system_prompt = self.template_parser.get("rag", "system_prompt")

        documents_prompts = "\n".join([
            self.template_parser.get("rag", "document_prompt", {
                    "doc_num": idx + 1,
                    "chunk_text": self.generation_client.process_text(doc.text),
            })
            for idx, doc in enumerate(retrieved_documents)
        ])

        footer_prompt = self.template_parser.get("rag", "footer_prompt", {
            "query": query
        })

        # step3: Construct Generation Client Prompts
        chat_history = [
            self.generation_client.construct_prompt(
                prompt=system_prompt,
                role=self.generation_client.enums.SYSTEM.value,
            )
        ]

        full_prompt = "\n\n".join([ documents_prompts,  footer_prompt])

        # step4: Retrieve the Answer
        answer = self.generation_client.generate_text(
            prompt=full_prompt,
            chat_history=chat_history
        )

        return answer, full_prompt, chat_history

    # ============ Tagged Single Collection Methods ============
    
    MAIN_COLLECTION_NAME = "main_collection"

    def index_into_vector_db_with_tags(self, chunks: List[DataChunk],
                                        chunks_ids: List[int],
                                        tags: List[str],
                                        do_reset: bool = False):
        """Index chunks into single collection with tags in metadata"""
        
        # step1: create collection if not exists
        _ = self.vectordb_client.create_collection(
            collection_name=self.MAIN_COLLECTION_NAME,
            embedding_size=self.embedding_client.embedding_size,
            do_reset=False,  # Never reset entire collection
        )

        # step2: if do_reset, delete only records with matching tags
        if do_reset:
            _ = self.vectordb_client.delete_by_tags(
                collection_name=self.MAIN_COLLECTION_NAME,
                tags=tags
            )

        # step3: manage items with tags in metadata (including tags_key for exact match)
        tags_key = "|".join(sorted(tags))
        texts = [c.chunk_text for c in chunks]
        metadata = [{"tags": tags, "tags_key": tags_key, **(c.chunk_metadata or {})} for c in chunks]
        
        vectors = self.embedding_client.embed_text(
            texts=texts,
            document_type=DocumentTypeEnum.DOCUMENT.value
        )

        # step4: insert into vector db
        _ = self.vectordb_client.insert_many(
            collection_name=self.MAIN_COLLECTION_NAME,
            texts=texts,
            metadata=metadata,
            vectors=vectors,
            record_ids=chunks_ids,
        )

        return True

    def search_vector_db_with_tags(self, text: str, tags: List[str] = None, limit: int = 10):
        """Search in single collection with optional tags filter"""
        
        # step1: get text embedding vector
        vector = self.embedding_client.embed_text(
            texts=[text],
            document_type=DocumentTypeEnum.QUERY.value
        )[0]

        if not vector or len(vector) == 0:
            return False

        # step2: do semantic search with filter
        results = self.vectordb_client.search_by_vector_with_filter(
            collection_name=self.MAIN_COLLECTION_NAME,
            vector=vector,
            limit=limit,
            tags=tags
        )

        if not results:
            return False

        return results

    def answer_rag_question_with_tags(self, query: str, tags: List[str] = None, limit: int = 10):
        """RAG answer using single collection with optional tags filter"""
        
        answer, full_prompt, chat_history = None, None, None

        # step1: retrieve related documents with tags filter
        retrieved_documents = self.search_vector_db_with_tags(
            text=query,
            tags=tags,
            limit=limit,
        )

        if not retrieved_documents or len(retrieved_documents) == 0:
            return answer, full_prompt, chat_history
        
        # step2: Construct LLM prompt
        system_prompt = self.template_parser.get("rag", "system_prompt")

        documents_prompts = "\n".join([
            self.template_parser.get("rag", "document_prompt", {
                    "doc_num": idx + 1,
                    "chunk_text": self.generation_client.process_text(doc.text),
            })
            for idx, doc in enumerate(retrieved_documents)
        ])

        footer_prompt = self.template_parser.get("rag", "footer_prompt", {
            "query": query
        })

        # step3: Construct Generation Client Prompts
        chat_history = [
            self.generation_client.construct_prompt(
                prompt=system_prompt,
                role=self.generation_client.enums.SYSTEM.value,
            )
        ]

        full_prompt = "\n\n".join([documents_prompts, footer_prompt])

        # step4: Retrieve the Answer
        answer = self.generation_client.generate_text(
            prompt=full_prompt,
            chat_history=chat_history
        )

        return answer, full_prompt, chat_history

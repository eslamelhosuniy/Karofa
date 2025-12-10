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

    # ============ Chat History Methods ============

    MAX_CHAT_HISTORY_MESSAGES = 5

    def format_chat_history_for_rewrite(self, chat_history: list) -> str:
        """Format chat history for query rewriting prompt"""
        if not chat_history or len(chat_history) == 0:
            return "No previous messages."
        
        # Take only last MAX_CHAT_HISTORY_MESSAGES messages
        recent_history = chat_history[-self.MAX_CHAT_HISTORY_MESSAGES:]
        
        formatted = []
        for msg in recent_history:
            role = "User" if msg.get("role") == "user" else "Assistant"
            formatted.append(f"{role}: {msg.get('content', '')}")
        
        return "\n".join(formatted)

    def rewrite_query_with_context(self, query: str, chat_history: list,
                                    session_entities: list = None) -> str:
        """Rewrites the query to include context from chat history"""
        
        if not chat_history or len(chat_history) == 0:
            return query

        # Format chat history
        formatted_history = self.format_chat_history_for_rewrite(chat_history)
        
        # Format session entities
        entities_str = ", ".join(session_entities) if session_entities else "None"

        # Get prompts from templates
        system_prompt = self.template_parser.get("chat", "query_rewrite_system")
        rewrite_prompt = self.template_parser.get("chat", "query_rewrite_prompt", {
            "chat_history": formatted_history,
            "session_entities": entities_str,
            "query": query
        })

        # Construct chat for LLM
        chat = [
            self.generation_client.construct_prompt(
                prompt=system_prompt,
                role=self.generation_client.enums.SYSTEM.value,
            )
        ]

        # Generate rewritten query
        rewritten_query = self.generation_client.generate_text(
            prompt=rewrite_prompt,
            chat_history=chat,
            max_output_tokens=500,
            temperature=0.3
        )

        if not rewritten_query:
            return query

        return rewritten_query.strip()

    def extract_session_entities(self, query: str, answer: str,
                                  existing_entities: list = None) -> list:
        """Extracts important entities from the conversation"""
        
        # Format existing entities
        entities_str = ", ".join(existing_entities) if existing_entities else "None"

        # Get prompts from templates
        system_prompt = self.template_parser.get("chat", "entity_extraction_system")
        extraction_prompt = self.template_parser.get("chat", "entity_extraction_prompt", {
            "query": query,
            "answer": answer[:500] if answer else "",  # Limit answer length
            "existing_entities": entities_str
        })

        # Construct chat for LLM
        chat = [
            self.generation_client.construct_prompt(
                prompt=system_prompt,
                role=self.generation_client.enums.SYSTEM.value,
            )
        ]

        # Generate entities
        entities_response = self.generation_client.generate_text(
            prompt=extraction_prompt,
            chat_history=chat,
            max_output_tokens=200,
            temperature=0.2
        )

        if not entities_response:
            return existing_entities or []

        # Parse JSON array from response
        try:
            import re
            # Extract JSON array from response
            match = re.search(r'\[.*?\]', entities_response, re.DOTALL)
            if match:
                new_entities = json.loads(match.group())
                if isinstance(new_entities, list):
                    # Merge with existing entities (add new ones, keep old ones)
                    merged_entities = list(existing_entities) if existing_entities else []
                    for entity in new_entities:
                        if entity not in merged_entities:
                            merged_entities.append(entity)
                    # Limit to 10 entities (keep most recent)
                    return merged_entities[-10:] if len(merged_entities) > 10 else merged_entities
        except (json.JSONDecodeError, Exception):
            pass

        return existing_entities or []

    def answer_rag_question_with_history(self, project, query: str,
                                          chat_history: list = None,
                                          session_entities: list = None,
                                          limit: int = 10):
        """RAG answer with chat history support using query rewriting"""
        
        answer, full_prompt, llm_chat_history = None, None, None
        rewritten_query = query
        updated_entities = session_entities or []

        # Step 1: Rewrite query if chat history exists
        if chat_history and len(chat_history) > 0:
            rewritten_query = self.rewrite_query_with_context(
                query=query,
                chat_history=chat_history,
                session_entities=session_entities
            )

        # Step 2: Retrieve related documents using rewritten query
        retrieved_documents = self.search_vector_db_collection(
            project=project,
            text=rewritten_query,
            limit=limit,
        )

        if not retrieved_documents or len(retrieved_documents) == 0:
            return answer, full_prompt, llm_chat_history, rewritten_query, updated_entities
        
        # Step 3: Construct LLM prompt
        system_prompt = self.template_parser.get("rag", "system_prompt")

        documents_prompts = "\n".join([
            self.template_parser.get("rag", "document_prompt", {
                    "doc_num": idx + 1,
                    "chunk_text": self.generation_client.process_text(doc.text),
            })
            for idx, doc in enumerate(retrieved_documents)
        ])

        footer_prompt = self.template_parser.get("rag", "footer_prompt", {
            "query": rewritten_query
        })

        # Step 4: Construct Generation Client Prompts with actual chat history
        llm_chat_history = [
            self.generation_client.construct_prompt(
                prompt=system_prompt,
                role=self.generation_client.enums.SYSTEM.value,
            )
        ]

        # Add actual chat history messages to LLM context
        if chat_history and len(chat_history) > 0:
            for msg in chat_history[-self.MAX_CHAT_HISTORY_MESSAGES:]:
                role = self.generation_client.enums.USER.value if msg.get("role") == "user" else self.generation_client.enums.ASSISTANT.value
                llm_chat_history.append(
                    self.generation_client.construct_prompt(
                        prompt=msg.get("content", ""),
                        role=role,
                    )
                )

        full_prompt = "\n\n".join([documents_prompts, footer_prompt])

        # Step 5: Retrieve the Answer
        answer = self.generation_client.generate_text(
            prompt=full_prompt,
            chat_history=llm_chat_history
        )

        # Step 6: Extract session entities from new conversation
        if answer:
            updated_entities = self.extract_session_entities(
                query=query,
                answer=answer,
                existing_entities=session_entities
            )

        return answer, full_prompt, llm_chat_history, rewritten_query, updated_entities

    def answer_rag_question_with_tags_and_history(self, query: str,
                                                   tags: list = None,
                                                   chat_history: list = None,
                                                   session_entities: list = None,
                                                   limit: int = 10):
        """RAG answer with tags and chat history support"""
        
        answer, full_prompt, llm_chat_history = None, None, None
        rewritten_query = query
        updated_entities = session_entities or []

        # Step 1: Rewrite query if chat history exists
        if chat_history and len(chat_history) > 0:
            rewritten_query = self.rewrite_query_with_context(
                query=query,
                chat_history=chat_history,
                session_entities=session_entities
            )

        # Step 2: Retrieve related documents with tags filter using rewritten query
        retrieved_documents = self.search_vector_db_with_tags(
            text=rewritten_query,
            tags=tags,
            limit=limit,
        )

        if not retrieved_documents or len(retrieved_documents) == 0:
            return answer, full_prompt, llm_chat_history, rewritten_query, updated_entities
        
        # Step 3: Construct LLM prompt
        system_prompt = self.template_parser.get("rag", "system_prompt")

        documents_prompts = "\n".join([
            self.template_parser.get("rag", "document_prompt", {
                    "doc_num": idx + 1,
                    "chunk_text": self.generation_client.process_text(doc.text),
            })
            for idx, doc in enumerate(retrieved_documents)
        ])

        footer_prompt = self.template_parser.get("rag", "footer_prompt", {
            "query": rewritten_query
        })

        # Step 4: Construct Generation Client Prompts with actual chat history
        llm_chat_history = [
            self.generation_client.construct_prompt(
                prompt=system_prompt,
                role=self.generation_client.enums.SYSTEM.value,
            )
        ]

        # Add actual chat history messages to LLM context
        if chat_history and len(chat_history) > 0:
            for msg in chat_history[-self.MAX_CHAT_HISTORY_MESSAGES:]:
                role = self.generation_client.enums.USER.value if msg.get("role") == "user" else self.generation_client.enums.ASSISTANT.value
                llm_chat_history.append(
                    self.generation_client.construct_prompt(
                        prompt=msg.get("content", ""),
                        role=role,
                    )
                )

        full_prompt = "\n\n".join([documents_prompts, footer_prompt])

        # Step 5: Retrieve the Answer
        answer = self.generation_client.generate_text(
            prompt=full_prompt,
            chat_history=llm_chat_history
        )

        # Step 6: Extract session entities from new conversation
        if answer:
            updated_entities = self.extract_session_entities(
                query=query,
                answer=answer,
                existing_entities=session_entities
            )

        return answer, full_prompt, llm_chat_history, rewritten_query, updated_entities

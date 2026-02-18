import streamlit as st
from config.settings import settings

# Nota: Importamos DocumentService en lugar de PDFService
from services.document_service import DocumentService
from services.embedding_service import EmbeddingService
from services.database_service import DatabaseService
from services.ai_service import AIService
from services.conversation_service import ConversationService

class ChatApp: # Le cambié el nombre a ChatApp (más genérico)
    def __init__(self):
        # 👇 Aquí usamos el nuevo servicio
        self.document_service = DocumentService()
        self.embedding_service = EmbeddingService()
        self.database_service = DatabaseService(self.embedding_service)
        self.ai_service = AIService()
        self.conversation_service = ConversationService()
    
    def initialize_session_state(self):
        if "document" not in st.session_state:
            st.session_state.document = None
        if "file_processed" not in st.session_state:
            st.session_state.file_processed = False
        if "file_hash" not in st.session_state:
            st.session_state.file_hash = None
        if "conversation_service" not in st.session_state:
            st.session_state.conversation_service = self.conversation_service
        if "database_service" not in st.session_state:
            st.session_state.database_service = None
    
    def process_document(self, uploaded_file):
        """Procesa cualquier archivo (PDF, DOCX, XLSX, TXT)"""
        with st.spinner(f"Procesando {uploaded_file.name}..."):
            # 👇 Usamos process_file del nuevo servicio
            document = self.document_service.process_file(uploaded_file, uploaded_file.name)
            
            # Crear colección en base de datos
            self.database_service.create_collection(document)
            
            # Guardar en sesión
            st.session_state.database_service = self.database_service
            st.session_state.document = document
            st.session_state.file_processed = True
            st.session_state.file_hash = document.file_hash
            
            # Limpiar historial al cambiar de documento
            st.session_state.conversation_service.clear_history()
        
        st.success(f"Archivo procesado: {len(document.chunks)} fragmentos generados.")
    
    def handle_question(self, question: str):
        with st.spinner("Pensando..."):
            db_service = st.session_state.database_service
            if db_service is None:
                st.error("Primero debes procesar un documento.")
                return "", None

            # Recuperar contexto relevante
            retrieval_result = db_service.retrieve_context(question)
            context_text = retrieval_result.get_context_text()
            
            history = st.session_state.conversation_service.get_history()
            
            # Generar respuesta
            answer = self.ai_service.generate_response(context_text, question, history)
            
            # Actualizar historial
            st.session_state.conversation_service.add_user_message(question)
            st.session_state.conversation_service.add_assistant_message(answer)
            
            return answer, retrieval_result
    
    def render_ui(self):
        st.title("Chat Multi-Formato")
        st.markdown("Soporta: **PDF, Excel (.xlsx), Word (.docx), Texto (.txt)**")
        
        # 👇 Widget actualizado para múltiples tipos
        uploaded_file = st.file_uploader("Sube tu archivo", type=["pdf", "docx", "xlsx", "txt"])
        
        if uploaded_file:
            # Calcular hash para detectar cambios de archivo
            current_hash = self.document_service.hash_file(uploaded_file)
            
            if st.session_state.file_hash != current_hash:
                st.session_state.file_hash = current_hash
                st.session_state.file_processed = False
                st.session_state.document = None
                st.session_state.database_service = None
                st.session_state.conversation_service.clear_history()
        
        # Botón de procesamiento
        if uploaded_file and not st.session_state.file_processed:
            if st.button("Procesar Archivo"):
                self.process_document(uploaded_file)
        
        # Área de chat
        if st.session_state.file_processed:
            st.divider()
            question = st.chat_input("Pregunta sobre tu documento...")
            
            if question:
                # Mostrar mensaje del usuario inmediatamente
                with st.chat_message("user"):
                    st.write(question)

                # Procesar y mostrar respuesta
                answer, retrieval_result = self.handle_question(question)
                
                if answer:
                    with st.chat_message("assistant"):
                        st.write(answer)
                        with st.expander("Ver contexto utilizado"):
                            for chunk in retrieval_result.chunks:
                                st.text(chunk)

    def run(self):
        st.set_page_config(page_title=settings.PAGE_TITLE, page_icon="📚")
        self.initialize_session_state()
        self.render_ui()

if __name__ == "__main__":
    app = ChatApp()
    app.run()
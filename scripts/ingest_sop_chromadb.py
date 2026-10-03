# importing the required libraries
from pathlib import Path

from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma

# defining the projects path
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

SOP_PATH = PROJECT_ROOT / "data" / "policy" / "chain_logistics.md"
CHROMA_PATH = PROJECT_ROOT / "data" / "chroma_sop"

MODEL_NAME = "BAAI/bge-m3"
HF_CACHE_DIR = Path.home() / ".cache" / "huggingface"

COLLECTION_NAME = "chain_logistics_sop"

# checking if the sop exists or not
if not SOP_PATH.is_file():
    raise FileNotFoundError(f"SOP file was not found at the location :{SOP_PATH} ")

CHROMA_PATH.mkdir(parents=True, exist_ok=True)

print(f"SOP file found: {SOP_PATH}")
print(f"Chroma storage location: {CHROMA_PATH}")

# loading the sop document
loader = TextLoader(
    str(SOP_PATH),
    encoding="utf-8",
)

documents = loader.load()
if not documents:
    raise ValueError("the sop file was loaded, but it contains no content ")

print(f"loaded {len(documents)} document object")

# Splitting the sop docuemnts into chunks
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=150,
    separators=[
        "\n##",
        "\n###",
        "\n\n",
        "\n",
        ".",
        " ",
        "",
    ],
)
chunks = text_splitter.split_documents(documents)

if not chunks:
    raise ValueError("No chunks were created from the SOP.")

print(f"Created {len(chunks)} SOP chunks")

# load the BGE-M3 embedding model
embeddings = HuggingFaceEmbeddings(
    model_name=MODEL_NAME,
    cache_folder=str(HF_CACHE_DIR / "sentence-transformers"),
    model_kwargs={"device": "cpu"},
    encode_kwargs={
        "normalize_embeddings": True,
    },
)

print(f"embedding model loaded: {MODEL_NAME}")

# creating chroma vector store

vector_store = Chroma(
    collection_name=COLLECTION_NAME,
    embedding_function=embeddings,
    persist_directory=str(CHROMA_PATH),
)

print(f"chroma collection ready: {COLLECTION_NAME}")

# adding metadata and stable IDs

for index, chunk in enumerate(chunks, start=1):
    chunk.metadata.update(
        {
            "source_file": SOP_PATH.name,
            "document_type": "standard_operating_procedure",
            "chunk_id": index,
        }
    )

chunk_ids = [f"sop-chunk-{index:05d}" for index in range(1, len(chunks) + 1)]

# storing the chunks in chroma db

vector_store.add_documents(
    documents=chunks,
    ids=chunk_ids,
)

print(f"Stored {len(chunks)} chunks in chromaDB")

# testing the semantic search

test_query = "what should we do when a shipment is delayed?"

search_results = vector_store.similarity_search(
    test_query,
    k=3,
)

print("\nTop search results:\n")

for result_number, result in enumerate(search_results, start=1):
    print(f"--- Result{result_number}---")
    print(f"metadata:{result.metadata}")
    print(result.page_content[:500])
    print()

import chromadb

import config

_client = chromadb.PersistentClient(path=config.DB_FOLDER)
_collection = _client.get_or_create_collection(name=config.COLLECTION_NAME)


def add_chunks(chunks, embeddings, username):
    print(f"saving {len(chunks)} chunks to chromadb for user {username}...")
    
    # create lists using standard loop
    chunk_ids = []
    chunk_docs = []
    chunk_metas = []
    for c in chunks:
        chunk_ids.append(c["id"])
        chunk_docs.append(c["text"])
        chunk_metas.append({
            "filename": c["filename"],
            "chunk_number": c["chunk_number"],
            "username": username
        })

    _collection.add(
        ids=chunk_ids,
        embeddings=embeddings,
        documents=chunk_docs,
        metadatas=chunk_metas,
    )



def query(query_embedding, username, top_k=5):
    print(f"querying vector store for user: {username}...")
    results = _collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        where={"username": username}
    )

    if not results["ids"] or not results["ids"][0]:
        return []

    sources = []
    for i in range(len(results["ids"][0])):
        sources.append({
            "text": results["documents"][0][i],
            "filename": results["metadatas"][0][i]["filename"],
            "chunk_number": results["metadatas"][0][i]["chunk_number"],
        })
    return sources


def has_documents(username):
    results = _collection.get(
        where={"username": username},
        limit=1
    )
    return len(results["ids"]) > 0


def delete_document(username, filename):
    print(f"deleting file '{filename}' for user '{username}' from chromadb...")
    # delete by username AND filename so we only touch this user's data
    _collection.delete(
        where={"$and": [{"username": username}, {"filename": filename}]}
    )



def list_user_documents(username):
    results = _collection.get(
        where={"username": username},
        include=["metadatas"]
    )
    if not results or not results["metadatas"]:
        return []
    filenames = set()
    for meta in results["metadatas"]:
        if meta and "filename" in meta:
            filenames.add(meta["filename"])
    return sorted(list(filenames))

from rag import RAGSystem

def main():
    rag = RAGSystem()

    question = "I forgot my password and cannot log into my account."

    results = rag.retrieve(question)

    print("\n--- Retrieved Results ---\n")

    for result in results:
        print(f"Source: {result['source']}")
        print(f"Score: {result['score']:.4f}")
        print(f"Content:\n{result['content']}")
        print("-" * 60)


if __name__ == "__main__":
    main()
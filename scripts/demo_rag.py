import argparse

from specialist.rag import RAGSystem


def main():
    parser = argparse.ArgumentParser(
        description="Retrieve and rerank support passages (no Groq/browser)."
    )
    parser.add_argument(
        "question",
        nargs="?",
        default="I forgot my password and cannot log into my account.",
    )
    question = parser.parse_args().question
    rag = RAGSystem()

    results = rag.retrieve(question)

    print("\n--- Retrieved Results ---\n")

    for result in results:
        print(f"Source: {result['source']}")
        print(f"Score: {result['score']:.4f}")
        print(f"Content:\n{result['content']}")
        print("-" * 60)


if __name__ == "__main__":
    main()

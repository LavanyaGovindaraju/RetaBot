"""CLI interface for the TechMart Support Agent."""

from __future__ import annotations

import sys
import os

# Ensure project root is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from agent.core import SupportAgent
from rag.engine import RAGEngine


def main():
    print("=" * 60)
    print(f"  Welcome to {config.COMPANY_NAME} Customer Support")
    print("  Type 'quit' or 'exit' to end the conversation.")
    print("  Type 'data' to see extracted information so far.")
    print("=" * 60)
    print()

    # Initialise RAG engine
    rag = None
    if config.RAG_ENABLED:
        try:
            rag = RAGEngine()
            rag.load()
            print("[RAG knowledge base loaded]\n")
        except Exception as e:
            print(f"[RAG disabled: {e}]\n")

    agent = SupportAgent(rag_engine=rag)

    # Initial greeting
    greeting = agent.chat("Hello")
    print(f"Agent: {greeting}\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            user_input = "quit"

        if not user_input:
            continue

        if user_input.lower() in ("quit", "exit"):
            print("\nEnding conversation...\n")
            record = agent.end_conversation()
            _print_summary(record)
            break

        if user_input.lower() == "data":
            _print_extracted(agent)
            continue

        try:
            reply = agent.chat(user_input)
        except KeyboardInterrupt:
            print("\n\nInterrupted. Saving conversation...")
            record = agent.end_conversation()
            _print_summary(record)
            break
        sentiment = agent.messages[-2].sentiment  # user message sentiment
        sent_tag = f" [{sentiment.value}]" if sentiment else ""
        print(f"Agent: {reply}{sent_tag}\n")


def _print_extracted(agent: SupportAgent):
    data = agent.get_extracted_data()
    comp = data.completeness()
    print("\n--- Extracted Information ---")
    print(f"  Order Number:   {data.order_number or '—'}")
    print(f"  Category:       {data.problem_category.value if data.problem_category else '—'}")
    print(f"  Description:    {data.problem_description or '—'}")
    print(f"  Urgency:        {data.urgency_level.value if data.urgency_level else '—'}")
    print(f"  Customer Name:  {data.customer_name or '—'}")
    print(f"  Email:          {data.customer_email or '—'}")
    print(f"  Product:        {data.product_name or '—'}")
    print(f"  Completeness:   {comp['pct']:.0f}% ({', '.join(comp['missing']) if comp['missing'] else 'all collected'})")
    print("---\n")


def _print_summary(record):
    print("=" * 60)
    print("  CONVERSATION SUMMARY")
    print("=" * 60)
    if record.summary:
        print(f"\n  {record.summary.summary}")
        if record.summary.key_points:
            print("\n  Key Points:")
            for kp in record.summary.key_points:
                print(f"    • {kp}")
        if record.summary.resolution:
            print(f"\n  Resolution: {record.summary.resolution}")
        if record.summary.overall_sentiment:
            print(f"  Overall Sentiment: {record.summary.overall_sentiment}")
    print()
    _print_extracted_from_record(record)
    print(f"\n  Conversation saved: {record.conversation_id}")
    print("=" * 60)


def _print_extracted_from_record(record):
    data = record.extracted_data
    print("  Extracted Data:")
    print(f"    Order Number:   {data.order_number or '—'}")
    print(f"    Category:       {data.problem_category.value if data.problem_category else '—'}")
    print(f"    Description:    {data.problem_description or '—'}")
    print(f"    Urgency:        {data.urgency_level.value if data.urgency_level else '—'}")
    print(f"    Customer Name:  {data.customer_name or '—'}")
    print(f"    Product:        {data.product_name or '—'}")


if __name__ == "__main__":
    main()

from app.services.retrieval import search_similar_chunks
from app.services.prompt import build_prompt
from app.services.llm import generate_answer

question = "How does Reanimation Protocols work?"



results = search_similar_chunks(question, top_k=5)

# print("\nStart Q1:\n")
# for i, result in enumerate(results, start=1):
#     print(f"\n=== RESULT {i} ===")
#     print(f"score: {result.score:.4f}")
#     print(f"heading: {result.heading}")
#     print(f"parent: {result.parent_heading}")
#     print(result.text[:800])
# print("\nEnd Q1\n")

prompt = build_prompt(question, results)
print("\nStart P1:\n")
print(prompt)
print("\nEnd P1:\n")
answer = generate_answer(prompt)

print("\nStart A1:\n")
print(answer)
print("\nEnd A1:\n")

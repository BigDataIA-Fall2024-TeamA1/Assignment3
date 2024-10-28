from langchain_nvidia_ai_endpoints import ChatNVIDIA

client = ChatNVIDIA(
  model="meta/llama-3.2-3b-instruct",
  api_key="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", 
  temperature=0.2,
  top_p=0.7,
  max_tokens=1024,
)

for chunk in client.stream([{"role":"user","content":"Write a limerick about the wonders of GPU computing."}]): 
  print(chunk.content, end="")

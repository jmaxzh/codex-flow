用户指令: {{ inputs.user_instruction }}
历史评审输出: {{ inputs.review_history }}

{{ prompt_file("./shared/" + inputs.role_prompt_file) }}

仅输出“本轮新增问题（含代码位置）”，不要重复历史中已发现的问题。
若无新增问题，pass=true，否则 pass=false，
最后一行输出严格 JSON object（不要使用代码块）：
{"pass": true/false}

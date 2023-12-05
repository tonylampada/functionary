import json

from llama_cpp import Llama
from transformers import AutoTokenizer

from functionary.prompt_template import get_prompt_template_from_tokenizer

llm = Llama(
    model_path="/Users/tony/work/solo/llmmodels/Functionary-7B-v1.4-GGUF.q8_0.gguf",  # from https://huggingface.co/meetkai/functionary-7b-v1.4-GGUF/tree/main
    # model_path="/Users/tony/work/solo/llmmodels/CodeLlama-7B-GGUF.gguf",  # from https://huggingface.co/meetkai/functionary-7b-v1.4-GGUF/tree/main
    n_ctx=4096,
    n_gpu_layers=-1,
)
tokenizer = AutoTokenizer.from_pretrained("meetkai/functionary-7b-v1.4", legacy=True)
# tokenizer = AutoTokenizer.from_pretrained("codellama/CodeLlama-7b-hf", legacy=True)

prompt_template = get_prompt_template_from_tokenizer(tokenizer)


class Chat:
    def __init__(self, systemprompt, functions, executor=None):
        self.messages = [{"role": "system", "content": systemprompt}]
        self.functions = functions
        self.executor = executor

    def sendChat(self, msg):
        self.messages.append({"role": "user", "content": msg})
        return self._send()

    def sendFnresult(self, name, result):
        self.messages.append(
            {
                "role": "function",
                "content": json.dumps(result),
                "name": name,
            }
        )
        return self._send()

    def _send(self):
        messages = self.messages[:]
        messages.append({"role": "assistant"})
        prompt_str = prompt_template.get_prompt_from_messages(messages, self.functions)
        token_ids = tokenizer.encode(prompt_str)
        gen_tokens = []
        stop_token_ids = [
            tokenizer.encode(token)[-1]
            for token in prompt_template.get_stop_tokens_for_generation()
        ]
        print("stop_token_ids: ", stop_token_ids)
        for token_id in llm.generate(token_ids, temp=0):
            if token_id in stop_token_ids:
                break
            gen_tokens.append(token_id)

        llm_output = tokenizer.decode(gen_tokens)

        result = prompt_template.parse_assistant_response(llm_output)
        print("DEBUG", result)
        self.messages.append(result)
        if self.executor and result.get("function_call"):
            fnresult = self.executor.execute(result["function_call"])
            result = self.sendFnresult(result["function_call"]["name"], fnresult)
        return result


class Executor:
    def __init__(self, functions):
        self.fnmap = {f.__name__: f for f in functions}

    def execute(self, function_call):
        name = function_call["name"]
        arguments = json.loads(function_call["arguments"])
        fn = self.fnmap[name]
        return fn(**arguments)


if __name__ == "__main__":
    functions = [
        {
            "name": "get_current_weather",
            "description": "Get the current weather in a given location",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "The city and state, e.g. San Francisco, CA",
                    },
                    "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]},
                },
                "required": ["location"],
            },
        }
    ]

    def get_current_weather(location, unit):
        print(f"getting weather for {location} in {unit}")
        return {"temperature": "25 degrees Celsius"}

    chat = Chat(functions, Executor([get_current_weather]))
    resp = chat.sendChat("what's the weather like in Hanoi?")
    print(resp)

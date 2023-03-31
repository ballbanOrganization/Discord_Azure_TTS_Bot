import openai


async def request_chatgpt_v1(prompt: str,
                             model: str = "text-davinci-003",
                             temperature: float = 0.5,
                             max_tokens: int = 1000,
                             show_all_response: bool = False
                             ) -> str:
    try:
        print(f'chatGPT log: prompt:{prompt}'
              f'model:{model} temperature:{temperature} max_tokens:{max_tokens} show_all_response:{show_all_response}')
        response = openai.Completion.create(model=model,
                                            prompt=prompt,
                                            temperature=temperature,
                                            max_tokens=max_tokens,
                                            n=1)
        return str(response) if show_all_response else response['choices'][0].text.strip()
    except Exception as e:
        return f"error:{e}"


async def request_chatgpt_v2(prompt: str,
                             model: str = "gpt-3.5-turbo",
                             show_all_response: bool = False,):
    try:
        print(f'chatGPT log: prompt:{prompt}'
              f'model:{model} show_all_response:{show_all_response}')
        response = openai.ChatCompletion.create(
            model=model,
            messages=[
                {'role': 'user', 'content': prompt}
            ]
        )
        return str(response) if show_all_response else response['choices'][0]['message']['content']
    except Exception as e:
        return f"error:{e}"

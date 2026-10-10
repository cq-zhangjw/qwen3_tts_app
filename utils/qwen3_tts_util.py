import os

import torch
import soundfile as sf
from qwen_tts import Qwen3TTSModel

from utils.sound_util import play_audio


def tts_by_speaker():

    model = Qwen3TTSModel.from_pretrained(
        r"E:\models\tts\qwen3-tts-12hz-1.7b-custom_voice",
        device_map="cuda:0",
        dtype=torch.bfloat16,
        # attn_implementation="flash_attention_2",
    )

    speakers = [
        "Vivian",  # 明亮年轻的女性声音
        "Serena",  # 温暖柔和的女性声音
        "Uncle_Fu",  # 沉稳的男性声音
        "Dylan",  # 北京口音男性
        "Eric",  # 四川口音男性
        "Ryan",  # 动态英语男声
        "Aiden",  # 美式英语男声
        "Ono_Anna",  # 日语女性声音
        "Sohee"  # 韩语女性声音
    ]

    # single inference
    wavs, sr = model.generate_custom_voice(
        text="其实我真的有发现，我是一个特别善于观察别人情绪的人。",
        language="Chinese", # Pass `Auto` (or omit) for auto language adaptive; if the target language is known, set it explicitly.
        speaker=speakers[1],
        instruct="用特别激昂的语气说", # Omit if not needed.
    )
    # sf.write("output_custom_voice.wav", wavs[0], sr)

    # sf.write("output_custom_voice_0.wav", wavs[0], sr)
    play_audio(wavs[0], sr)


def create_voice(text: str, prompt: str, voice_name: str, language: str = "Chinese"):
    print("create_voice...")
    model = Qwen3TTSModel.from_pretrained(
        r"E:\models\tts\qwen3-tts-12hz-1.7b-voice_design",
        device_map="cuda:0",
        dtype=torch.bfloat16,
        # attn_implementation="flash_attention_2",
    )

    # single inference
    wavs, sr = model.generate_voice_design(
        text=text,
        language=language,
        instruct=prompt,
    )

    save_file = f"./web/audio/{voice_name}.wav"
    os.makedirs(os.path.dirname(save_file), exist_ok=True)

    sf.write(save_file, wavs[0], sr)

    return f"/audio/{voice_name}.wav"



def test3():
    model = Qwen3TTSModel.from_pretrained(
        r"E:\models\tts\qwen3-tts-12hz-1.7b-base",
        device_map="cuda:0",
        dtype=torch.bfloat16,
        # attn_implementation="flash_attention_2",
    )


    ref_audio = "doubao.wav"
    ref_text = """
    大家好，我性格沉稳热忱，待人真诚坦荡，平日里热爱生活亦勤于钻研。闲暇时钟情品读文字、深耕学识，也乐于奔赴山野感受烟火美好。做事踏实有担当，处事谦和懂分寸，善于倾听交流，也能沉心直面挑战。始终心怀热忱奔赴前路，以真诚待人，以笃定行事，在平凡日子里坚守初心，稳步奔赴属于自己的远方。
    """

    prompt_items = model.create_voice_clone_prompt(
        ref_audio=ref_audio,
        ref_text=ref_text,
        x_vector_only_mode=False,
    )

    wavs, sr = model.generate_voice_clone(
        text="""
        什么玩艺，不就是和总裁有一腿吗，平时仗着这个，连总经理都不放在眼里。
我生了一肚子闷气，发现旁边还有一个没吃完的汉堡，随手抓过来就啃。""",
        language="Chinese",
        # ref_audio=ref_audio,
        # ref_text=ref_text,
        voice_clone_prompt=prompt_items
    )
    sf.write("../output_voice_clone.wav", wavs[0], sr)


if __name__ == '__main__':
    tts_by_speaker()
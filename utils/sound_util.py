import numpy as np
import soundfile as sf
import pygame
import tempfile
from pathlib import Path

# 初始化 pygame 音频（只初始化一次）
pygame.mixer.init()


def play_audio(wav: np.ndarray, sample_rate: int = 44100) -> None:
    """
    播放音频（无编译报错版）
    :param wav: numpy 数组 shape (1, num_samples,) float32
    """
    # 压缩维度 (1, N) → (N,)
    audio_data = wav.squeeze()

    # 创建临时 wav 文件（pygame 只能播放文件，不直接播放数组）
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        sf.write(tmp.name, audio_data, sample_rate)
        tmp_path = tmp.name

    # 加载并播放
    pygame.mixer.music.load(tmp_path)
    pygame.mixer.music.play()

    # 等待播放完成
    while pygame.mixer.music.get_busy():
        pygame.time.Clock().tick(10)

    # 清理临时文件
    # Path(tmp_path).unlink()


def save_audio(
        wav: np.ndarray,
        output_path: str,
        sample_rate: int = 44100,
        format: str = "mp3"  # 支持：mp3, wav, flac, ogg 等
) -> None:
    """
    保存音频文件，格式由参数指定，默认 mp3
    :param wav: numpy 数组，shape (1, num_samples,)，dtype=np.float32
    :param output_path: 输出文件路径（不含后缀会自动补全）
    :param sample_rate: 采样率，默认 44100 Hz
    :param format: 保存格式，默认 mp3
    """
    # 压缩维度
    audio_data = wav.squeeze()

    # 处理路径：自动补全后缀
    path = Path(output_path)
    if path.suffix.lower() != f".{format.lower()}":
        output_path = f"{path.stem}.{format.lower()}"

    # 保存音频（soundfile 自动根据后缀判断格式）
    sf.write(output_path, audio_data, sample_rate)
    print(f"✅ 音频已保存：{output_path}")


from pydub import AudioSegment
import os


def m4a_to_wav(input_m4a: str, output_wav: str = None) -> str:
    """
    将 m4a 音频文件转换为 wav 格式
    :param input_m4a: 输入的 m4a 文件路径
    :param output_wav: 输出的 wav 文件路径（不填则自动生成同名 wav）
    :return: 转换后的 wav 文件路径
    """
    # 自动生成输出路径
    if output_wav is None:
        output_wav = os.path.splitext(input_m4a)[0] + ".wav"

    # 加载 m4a 并导出为 wav
    audio = AudioSegment.from_file(input_m4a, format="m4a")
    audio.export(output_wav, format="wav")

    print(f"✅ 转换完成：{output_wav}")
    return output_wav


import soundcard as sc
import soundfile as sf


def record_system_audio(output_path: str = "doubao.wav", sample_rate: int = 44100):
    """
    录制电脑系统声音（内部声音）
    按 Ctrl + C 即可停止并自动保存
    """
    audio_data = []
    print("=" * 50)
    print("🎙️  系统声音录制中... 【按 Ctrl + C 停止并保存】")
    print("=" * 50)

    try:
        # 核心：获取系统回录麦克风（录内部声音）
        with sc.get_microphone(id=str(sc.default_speaker().name), include_loopback=True).recorder(
                samplerate=sample_rate) as mic:
            while True:
                # 持续录制，每次录0.1秒拼接
                chunk = mic.record(numframes=int(sample_rate * 0.1))
                audio_data.append(chunk)
                # 打印录制时长
                total_sec = len(audio_data) * 0.1
                print(f"\r⏱️  已录制：{total_sec:.1f} 秒", end="")

    except KeyboardInterrupt:
        # 用户按 Ctrl+C 触发这里
        print("\n\n🛑 录制停止，正在保存文件...")

        # 拼接所有音频
        full_audio = np.concatenate(audio_data, axis=0)

        # 保存
        sf.write(output_path, full_audio, sample_rate)
        print(f"✅ 音频已保存：{output_path}")
        print(f"📏 总时长：{len(full_audio) / sample_rate:.1f} 秒")


if __name__ == '__main__':
    # m4a_to_wav("../doubao.m4a", "../doubao.wav")
    record_system_audio()

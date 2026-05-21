import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Voice push-to-talk (plan section 6.2).
 *
 * Transcription is fully local via the browser Web Speech API — nothing
 * is sent to any third party (tenet T-12, invariant I-1). When the API
 * is unavailable the consuming surface falls back to text entry; voice
 * always has a visual + textual analog.
 */

interface SpeechRecognitionAlternative {
  readonly transcript: string;
}
interface SpeechRecognitionResult {
  readonly 0: SpeechRecognitionAlternative;
  readonly isFinal: boolean;
}
interface SpeechRecognitionEventLike {
  readonly results: ArrayLike<SpeechRecognitionResult>;
}
interface SpeechRecognitionLike {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  start(): void;
  stop(): void;
  onresult: ((event: SpeechRecognitionEventLike) => void) | null;
  onend: (() => void) | null;
  onerror: ((event: unknown) => void) | null;
}
type SpeechRecognitionCtor = new () => SpeechRecognitionLike;

function getRecognitionCtor(): SpeechRecognitionCtor | null {
  if (typeof window === "undefined") return null;
  const w = window as unknown as {
    SpeechRecognition?: SpeechRecognitionCtor;
    webkitSpeechRecognition?: SpeechRecognitionCtor;
  };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

export interface VoicePTT {
  readonly supported: boolean;
  readonly recording: boolean;
  readonly transcript: string;
  start: () => void;
  stop: () => void;
  reset: () => void;
}

export function useVoicePTT(): VoicePTT {
  const ctorRef = useRef<SpeechRecognitionCtor | null>(getRecognitionCtor());
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);
  const [recording, setRecording] = useState(false);
  const [transcript, setTranscript] = useState("");

  const stop = useCallback(() => {
    recognitionRef.current?.stop();
    setRecording(false);
  }, []);

  const start = useCallback(() => {
    const Ctor = ctorRef.current;
    if (!Ctor) return;
    const recognition = new Ctor();
    recognition.lang = "en-IN";
    recognition.interimResults = true;
    recognition.continuous = true;
    recognition.onresult = (event) => {
      let text = "";
      for (let i = 0; i < event.results.length; i += 1) {
        text += event.results[i]?.[0]?.transcript ?? "";
      }
      setTranscript(text.trim());
    };
    recognition.onend = () => setRecording(false);
    recognition.onerror = () => setRecording(false);
    recognitionRef.current = recognition;
    recognition.start();
    setRecording(true);
  }, []);

  const reset = useCallback(() => setTranscript(""), []);

  useEffect(() => () => recognitionRef.current?.stop(), []);

  return {
    supported: ctorRef.current !== null,
    recording,
    transcript,
    start,
    stop,
    reset,
  };
}

"use client";

import { useEffect, useRef, useState } from "react";
import styles from "./SplitFlap.module.css";

const CYCLE_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ";
const FLIP_MS = 45;
const STAGGER_MS = 35;
const WIDTH = 12; // fits the longest status label, "INTERVIEWING"

function pad(text: string): string {
  return text.padEnd(WIDTH, " ").slice(0, WIDTH);
}

interface SplitFlapProps {
  text: string;
  className?: string;
}

export function SplitFlap({ text, className }: SplitFlapProps) {
  const target = pad(text);
  const [display, setDisplay] = useState(target);
  const prevTarget = useRef(target);

  useEffect(() => {
    if (prevTarget.current === target) return;
    prevTarget.current = target;

    const timers: ReturnType<typeof setTimeout>[] = [];
    const chars = target.split("");

    chars.forEach((ch, i) => {
      const spins = ch === " " ? 1 : 3 + Math.floor(Math.random() * 3);
      let count = 0;

      const tick = () => {
        setDisplay((prev) => {
          const arr = prev.split("");
          arr[i] =
            count < spins - 1
              ? CYCLE_CHARS[Math.floor(Math.random() * CYCLE_CHARS.length)]
              : ch;
          return arr.join("");
        });
        count++;
        if (count < spins) {
          timers.push(setTimeout(tick, FLIP_MS));
        }
      };

      timers.push(setTimeout(tick, i * STAGGER_MS));
    });

    return () => timers.forEach(clearTimeout);
  }, [target]);

  return (
    <span className={`${styles.board} ${className ?? ""}`} aria-label={text}>
      {display.split("").map((ch, i) => (
        // eslint-disable-next-line react/no-array-index-key
        <span key={i} className={styles.tile}>
          {ch === " " ? "\u00A0" : ch}
        </span>
      ))}
    </span>
  );
}

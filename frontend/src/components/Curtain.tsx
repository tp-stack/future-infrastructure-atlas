import { useCallback, useEffect, useRef } from "react";

type CurtainSide = "left" | "right";

interface CurtainProps {
  side: CurtainSide;
  open: boolean;
  width?: number;
  onClose?: () => void;
  children: React.ReactNode;
}

export default function Curtain({ side, open, width = 380, onClose, children }: CurtainProps) {
  const curtainRef = useRef<HTMLDivElement>(null);

  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    if (e.key === "Escape" && open && onClose) {
      onClose();
    }
  }, [open, onClose]);

  useEffect(() => {
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [handleKeyDown]);

  return (
    <>
      {open && onClose && (
        <div
          className="curtain-overlay"
          onClick={onClose}
          aria-hidden="true"
        />
      )}
      <div
        ref={curtainRef}
        className={`curtain curtain--${side} ${open ? "curtain--open" : ""}`}
        style={{ width, maxWidth: "90vw" }}
        role="dialog"
        aria-modal={open ? "true" : undefined}
        aria-hidden={!open}
      >
        <div className="curtain-inner">
          {children}
        </div>
      </div>
    </>
  );
}

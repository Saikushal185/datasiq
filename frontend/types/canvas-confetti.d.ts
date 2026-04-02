declare module "canvas-confetti" {
  type ConfettiOrigin = {
    x?: number;
    y?: number;
  };

  type ConfettiOptions = {
    particleCount?: number;
    spread?: number;
    startVelocity?: number;
    origin?: ConfettiOrigin;
  };

  export default function confetti(options?: ConfettiOptions): void;
}

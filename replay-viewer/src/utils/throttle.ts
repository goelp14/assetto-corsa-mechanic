export function throttle<T extends (...args: never[]) => void>(fn: T, ms: number): T {
  let last = 0;
  let timer: ReturnType<typeof setTimeout> | null = null;
  let pending: Parameters<T> | null = null;

  const run = () => {
    if (!pending) return;
    const args = pending;
    pending = null;
    last = Date.now();
    fn(...args);
  };

  return ((...args: Parameters<T>) => {
    pending = args;
    const now = Date.now();
    const wait = ms - (now - last);
    if (wait <= 0) {
      if (timer) {
        clearTimeout(timer);
        timer = null;
      }
      run();
    } else if (!timer) {
      timer = setTimeout(() => {
        timer = null;
        run();
      }, wait);
    }
  }) as T;
}

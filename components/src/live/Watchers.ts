/**
 * A list of subscribers with safe fan-out.
 *
 * Every registry we keep - contact watchers, the store's asset watchers,
 * socket connection listeners - hands events to page components we don't
 * control, so they all need the same three things: one subscriber throwing
 * can't cost the others their delivery, a delivery iterates a snapshot so
 * unsubscribing mid-fan-out doesn't shift the list underneath it, and
 * unsubscribing twice does nothing the second time.
 *
 * The subscriber record and how an event reaches it belong to the caller -
 * interests, payloads and arities differ - so this owns only the list and the
 * delivery discipline.
 */
export class Watchers<W> {
  private watchers: W[] = [];

  // names the subscriber when reporting one that threw
  private label: string;

  constructor(label: string) {
    this.label = label;
  }

  public get size(): number {
    return this.watchers.length;
  }

  public has(watcher: W): boolean {
    return this.watchers.includes(watcher);
  }

  public some(predicate: (watcher: W) => boolean): boolean {
    return this.watchers.some(predicate);
  }

  /** A snapshot, for callers that need to read across everyone registered. */
  public all(): W[] {
    return [...this.watchers];
  }

  public add(watcher: W): void {
    this.watchers.push(watcher);
  }

  /** Removes it, reporting whether it was still registered. */
  public remove(watcher: W): boolean {
    const index = this.watchers.indexOf(watcher);
    if (index < 0) {
      return false;
    }
    this.watchers.splice(index, 1);
    return true;
  }

  public clear(): void {
    this.watchers.length = 0;
  }

  /** One delivery, with a subscriber's failure kept to itself. */
  public deliver(watcher: W, deliver: (watcher: W) => void): void {
    try {
      deliver(watcher);
    } catch (error) {
      console.error(`${this.label} failed`, error);
    }
  }

  /** Delivers to everyone registered now, or just those matching. */
  public each(
    deliver: (watcher: W) => void,
    matches?: (watcher: W) => boolean
  ): void {
    for (const watcher of this.all()) {
      if (!matches || matches(watcher)) {
        this.deliver(watcher, deliver);
      }
    }
  }

  /**
   * An initial delivery to one subscriber, off the current task so it lands
   * the way a live one would rather than before they can use the handle they
   * are being given. Skipped if they leave before it lands.
   */
  public prime(watcher: W, deliver: (watcher: W) => void): void {
    Promise.resolve().then(() => {
      if (this.has(watcher)) {
        this.deliver(watcher, deliver);
      }
    });
  }
}

import { expect, fixture } from '@open-wc/testing';
import { render } from 'lit-html';
import { renderAudioPlayer } from '../src/flow/actions/audio-player';

// a stand-in for HTMLAudioElement that lets tests drive playback events
class FakeAudio {
  public static created: FakeAudio[] = [];

  public src: string;
  public paused = true;
  public currentTime = 0;
  public duration = 0;
  public playCalls = 0;
  public pauseCalls = 0;
  public playRejects = false;

  private listeners: Record<string, (() => void)[]> = {};

  constructor(url: string) {
    this.src = url;
    FakeAudio.created.push(this);
  }

  public addEventListener(type: string, handler: () => void) {
    (this.listeners[type] ??= []).push(handler);
  }

  public play(): Promise<void> {
    this.playCalls++;
    if (this.playRejects) {
      return Promise.reject(new Error('blocked'));
    }
    this.paused = false;
    return Promise.resolve();
  }

  public pause() {
    this.pauseCalls++;
    this.paused = true;
  }

  public fire(type: string) {
    (this.listeners[type] || []).forEach((handler) => handler());
  }
}

const mount = async (url: string): Promise<HTMLElement> => {
  const host = (await fixture('<div></div>')) as HTMLElement;
  render(renderAudioPlayer(url), host);
  return host.querySelector('.audio-player') as HTMLElement;
};

const playButton = (player: HTMLElement) =>
  player.querySelector('.audio-play-btn') as HTMLElement;

const progressBar = (player: HTMLElement) =>
  player.querySelector('.audio-progress') as HTMLElement;

const isPauseIcon = (player: HTMLElement) =>
  playButton(player).innerHTML.includes('<rect');

const click = (element: HTMLElement) =>
  element.dispatchEvent(new MouseEvent('click', { bubbles: true }));

describe('flow/actions/audio-player', () => {
  let originalAudio: any;

  beforeEach(() => {
    originalAudio = (window as any).Audio;
    (window as any).Audio = FakeAudio;
    FakeAudio.created = [];
  });

  afterEach(() => {
    (window as any).Audio = originalAudio;
  });

  describe('rendering', () => {
    it('renders the player with its url and controls', async () => {
      const player = await mount('http://example.com/clip.mp3');
      expect(player.dataset.url).to.equal('http://example.com/clip.mp3');
      expect(playButton(player)).to.not.equal(null);
      expect(progressBar(player)).to.not.equal(null);
      expect(progressBar(player).style.width).to.equal('0%');
    });

    it('starts with the play icon', async () => {
      const player = await mount('http://example.com/clip.mp3');
      expect(playButton(player).querySelector('polygon')).to.not.equal(null);
      expect(isPauseIcon(player)).to.equal(false);
    });

    it('stops mouse events from reaching the canvas underneath', async () => {
      const player = await mount('http://example.com/clip.mp3');
      let bubbled = 0;
      document.addEventListener('mousedown', () => bubbled++);
      player.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
      expect(bubbled).to.equal(0);
    });
  });

  describe('playback', () => {
    it('creates an audio element for the url and starts playing', async () => {
      const player = await mount('http://example.com/clip.mp3');
      click(playButton(player));
      expect(FakeAudio.created).to.have.length(1);
      expect(FakeAudio.created[0].src).to.equal('http://example.com/clip.mp3');
      expect(FakeAudio.created[0].playCalls).to.equal(1);
      expect(isPauseIcon(player)).to.equal(true);
    });

    it('pauses when clicked while playing', async () => {
      const player = await mount('http://example.com/clip.mp3');
      click(playButton(player));
      click(playButton(player));
      expect(FakeAudio.created).to.have.length(1);
      expect(FakeAudio.created[0].pauseCalls).to.equal(1);
      expect(isPauseIcon(player)).to.equal(false);
    });

    it('restarts after being paused', async () => {
      const player = await mount('http://example.com/clip.mp3');
      click(playButton(player));
      click(playButton(player));
      click(playButton(player));
      // a fresh audio element is created for the restart
      expect(FakeAudio.created).to.have.length(2);
      expect(isPauseIcon(player)).to.equal(true);
    });

    it('does nothing without a url', async () => {
      const player = await mount('http://example.com/clip.mp3');
      delete player.dataset.url;
      click(playButton(player));
      expect(FakeAudio.created).to.have.length(0);
    });

    it('advances the progress bar as the clip plays', async () => {
      const player = await mount('http://example.com/clip.mp3');
      click(playButton(player));
      const audio = FakeAudio.created[0];
      audio.duration = 10;
      audio.currentTime = 2.5;
      audio.fire('timeupdate');
      expect(progressBar(player).style.width).to.equal('25%');
    });

    it('leaves the progress bar alone when the duration is unknown', async () => {
      const player = await mount('http://example.com/clip.mp3');
      click(playButton(player));
      FakeAudio.created[0].fire('timeupdate');
      expect(progressBar(player).style.width).to.equal('0%');
    });
  });

  describe('resetting', () => {
    it('resets when the clip ends', async () => {
      const player = await mount('http://example.com/clip.mp3');
      click(playButton(player));
      const audio = FakeAudio.created[0];
      audio.duration = 10;
      audio.currentTime = 5;
      audio.fire('timeupdate');
      expect(progressBar(player).style.width).to.equal('50%');

      audio.fire('ended');
      expect(isPauseIcon(player)).to.equal(false);
      expect(progressBar(player).style.width).to.equal('0%');
    });

    it('resets when the clip errors', async () => {
      const player = await mount('http://example.com/clip.mp3');
      click(playButton(player));
      FakeAudio.created[0].fire('error');
      expect(isPauseIcon(player)).to.equal(false);
      expect(progressBar(player).style.width).to.equal('0%');
    });

    it('resets when playback is refused', async () => {
      const player = await mount('http://example.com/clip.mp3');
      (window as any).Audio = class extends FakeAudio {
        public playRejects = true;
      };
      click(playButton(player));
      // let the rejected play promise settle
      await Promise.resolve();
      await Promise.resolve();
      expect(isPauseIcon(player)).to.equal(false);
      expect(progressBar(player).style.width).to.equal('0%');
    });
  });

  describe('single active player', () => {
    it('stops the previous clip when another starts', async () => {
      const first = await mount('http://example.com/one.mp3');
      const second = await mount('http://example.com/two.mp3');

      click(playButton(first));
      const firstAudio = FakeAudio.created[0];
      firstAudio.duration = 10;
      firstAudio.currentTime = 5;
      firstAudio.fire('timeupdate');
      expect(progressBar(first).style.width).to.equal('50%');

      click(playButton(second));

      expect(firstAudio.pauseCalls).to.equal(1);
      expect(firstAudio.currentTime).to.equal(0);
      // the first player is returned to its resting state
      expect(isPauseIcon(first)).to.equal(false);
      expect(progressBar(first).style.width).to.equal('0%');
      // and the second is now playing
      expect(isPauseIcon(second)).to.equal(true);
    });
  });
});

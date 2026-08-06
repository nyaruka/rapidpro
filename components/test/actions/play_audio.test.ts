import { expect } from '@open-wc/testing';
import { play_audio } from '../../src/flow/actions/play_audio';
import { PlayAudio } from '../../src/store/flow-definition';
import { ActionTest } from '../ActionHelper';
import {
  resolveToLocalizationFormData,
  resolveFromLocalizationFormData
} from '../../src/flow/utils';

/**
 * Test suite for the play_audio action configuration.
 */
describe('play_audio action config', () => {
  const helper = new ActionTest(play_audio, 'play_audio');

  describe('basic properties', () => {
    helper.testBasicProperties();

    it('has correct name', () => {
      expect(play_audio.name).to.equal('Play Recording');
    });

    it('is voice-only', () => {
      expect(play_audio.flowTypes).to.deep.equal(['voice']);
    });
  });

  describe('action scenarios', () => {
    helper.testAction(
      {
        uuid: 'test-play-1',
        type: 'play_audio',
        audio_url: '@results.voicemail'
      } as PlayAudio,
      'expression-url'
    );

    helper.testAction(
      {
        uuid: 'test-play-2',
        type: 'play_audio',
        audio_url: 'https://example.com/greeting.mp3'
      } as PlayAudio,
      'static-url'
    );
  });

  describe('data transformation', () => {
    it('converts action to form data', () => {
      const action: PlayAudio = {
        uuid: 'test-action',
        type: 'play_audio',
        audio_url: '@results.voicemail'
      };

      const formData = play_audio.toFormData!(action);
      expect(formData.uuid).to.equal('test-action');
      expect(formData.audio_url).to.equal('@results.voicemail');
    });

    it('handles missing audio_url', () => {
      const action = {
        uuid: 'test-action',
        type: 'play_audio'
      } as PlayAudio;

      const formData = play_audio.toFormData!(action);
      expect(formData.audio_url).to.equal('');
    });

    it('converts form data to action', () => {
      const formData = {
        uuid: 'test-action',
        audio_url: '@results.voicemail'
      };

      const action = play_audio.fromFormData!(formData) as PlayAudio;
      expect(action.uuid).to.equal('test-action');
      expect(action.type).to.equal('play_audio');
      expect(action.audio_url).to.equal('@results.voicemail');
    });

    it('trims whitespace from audio_url', () => {
      const formData = {
        uuid: 'test-action',
        audio_url: '  @results.voicemail  '
      };

      const action = play_audio.fromFormData!(formData) as PlayAudio;
      expect(action.audio_url).to.equal('@results.voicemail');
    });
  });

  describe('localization', () => {
    it('converts localization to form data', () => {
      const action: PlayAudio = {
        uuid: 'test-action',
        type: 'play_audio',
        audio_url: '@results.voicemail'
      };

      const localization = {
        audio_url: ['@results.voicemail_es']
      };

      const formData = resolveToLocalizationFormData(play_audio)!(
        action,
        localization
      );
      expect(formData.audio_url).to.equal('@results.voicemail_es');
    });

    it('handles missing localization', () => {
      const action: PlayAudio = {
        uuid: 'test-action',
        type: 'play_audio',
        audio_url: '@results.voicemail'
      };

      const formData = resolveToLocalizationFormData(play_audio)!(action, {});
      expect(formData.audio_url).to.equal('');
    });

    it('converts form data to localization', () => {
      const action: PlayAudio = {
        uuid: 'test-action',
        type: 'play_audio',
        audio_url: '@results.voicemail'
      };

      const formData = {
        uuid: 'test-action',
        audio_url: '@results.voicemail_es'
      };

      const localization = resolveFromLocalizationFormData(play_audio)!(
        formData,
        action
      );
      expect(localization.audio_url).to.deep.equal(['@results.voicemail_es']);
    });

    it('omits unchanged localization', () => {
      const action: PlayAudio = {
        uuid: 'test-action',
        type: 'play_audio',
        audio_url: '@results.voicemail'
      };

      const formData = {
        uuid: 'test-action',
        audio_url: '@results.voicemail' // same as original
      };

      const localization = resolveFromLocalizationFormData(play_audio)!(
        formData,
        action
      );
      expect(localization.audio_url).to.be.undefined;
    });
  });
});

import { expect } from '@open-wc/testing';
import { NODE_CONFIG } from '../src/flow/config';

describe('Backwards Compatibility', () => {
  describe('split_by_run_result_delimited alias', () => {
    it('should map split_by_run_result_delimited to split_by_run_result config', () => {
      // verify the alias exists in NODE_CONFIG
      expect(NODE_CONFIG['split_by_run_result_delimited']).to.exist;

      // verify it points to the same config as split_by_run_result
      expect(NODE_CONFIG['split_by_run_result_delimited']).to.equal(
        NODE_CONFIG['split_by_run_result']
      );
    });

    it('should have the correct type on the split_by_run_result config', () => {
      const config = NODE_CONFIG['split_by_run_result'];
      expect(config.type).to.equal('split_by_run_result');
    });

    it('should declare the alias in the config', () => {
      const config = NODE_CONFIG['split_by_run_result'];
      expect(config.aliases).to.exist;
      expect(config.aliases).to.include('split_by_run_result_delimited');
    });

    it('should allow old flows with split_by_run_result_delimited type to load', () => {
      // simulate loading an old flow with the delimited type
      const oldType = 'split_by_run_result_delimited';
      const config = NODE_CONFIG[oldType];

      expect(config).to.exist;
      expect(config.name).to.equal('Split by Result');
      expect(config.group).to.equal('split');
    });
  });
});

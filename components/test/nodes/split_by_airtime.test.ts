import { expect } from '@open-wc/testing';
import { split_by_airtime } from '../../src/flow/nodes/split_by_airtime';
import { Node, TransferAirtime } from '../../src/store/flow-definition';
import { NodeTest } from '../NodeHelper';

/**
 * Test suite for the split_by_airtime node configuration.
 */
describe('split_by_airtime node config', () => {
  const helper = new NodeTest(split_by_airtime, 'split_by_airtime');

  describe('basic properties', () => {
    helper.testBasicProperties();

    it('has correct name', () => {
      expect(split_by_airtime.name).to.equal('Send Airtime');
    });

    it('has correct type', () => {
      expect(split_by_airtime.type).to.equal('split_by_airtime');
    });

    it('should show as action', () => {
      expect(split_by_airtime.showAsAction).to.be.true;
    });
  });

  describe('toFormData', () => {
    it('should transform node with single currency to form data correctly', () => {
      const node: Node = {
        uuid: 'test-node-uuid',
        actions: [
          {
            type: 'transfer_airtime',
            uuid: 'action-uuid',
            amounts: {
              USD: 10
            }
          } as TransferAirtime
        ],
        router: {
          type: 'switch',
          operand: '@locals._new_transfer',
          cases: [
            {
              uuid: 'case-1',
              type: 'has_text',
              arguments: [],
              category_uuid: 'cat-success'
            }
          ],
          categories: [
            { uuid: 'cat-success', name: 'Success', exit_uuid: 'exit-success' },
            { uuid: 'cat-failure', name: 'Failure', exit_uuid: 'exit-failure' }
          ],
          default_category_uuid: 'cat-failure'
        },
        exits: [
          { uuid: 'exit-success', destination_uuid: null },
          { uuid: 'exit-failure', destination_uuid: null }
        ]
      };

      const formData = split_by_airtime.toFormData!(node);

      expect(formData.uuid).to.equal('test-node-uuid');
      expect(formData.amounts).to.have.lengthOf(1);
      expect(formData.amounts[0].currency[0].value).to.equal('USD');
      expect(formData.amounts[0].currency[0].name).to.equal('US Dollar (USD)');
      expect(formData.amounts[0].amount).to.equal('10');
      expect(formData.result_name).to.equal('');
    });

    it('should transform node with multiple currencies to form data correctly', () => {
      const node: Node = {
        uuid: 'test-node-uuid',
        actions: [
          {
            type: 'transfer_airtime',
            uuid: 'action-uuid',
            amounts: {
              USD: 10,
              EUR: 15,
              GBP: 8
            }
          } as TransferAirtime
        ],
        router: {
          type: 'switch',
          operand: '@locals._new_transfer',
          cases: [
            {
              uuid: 'case-1',
              type: 'has_text',
              arguments: [],
              category_uuid: 'cat-success'
            }
          ],
          categories: [
            { uuid: 'cat-success', name: 'Success', exit_uuid: 'exit-success' },
            { uuid: 'cat-failure', name: 'Failure', exit_uuid: 'exit-failure' }
          ],
          default_category_uuid: 'cat-failure'
        },
        exits: [
          { uuid: 'exit-success', destination_uuid: null },
          { uuid: 'exit-failure', destination_uuid: null }
        ]
      };

      const formData = split_by_airtime.toFormData!(node);

      expect(formData.uuid).to.equal('test-node-uuid');
      expect(formData.amounts).to.have.lengthOf(3);

      // Check currencies are present (order not guaranteed in object iteration)
      const currencies = formData.amounts.map((a: any) => a.currency[0].value);
      expect(currencies).to.include('USD');
      expect(currencies).to.include('EUR');
      expect(currencies).to.include('GBP');
    });

    it('should handle result_name in toFormData', () => {
      const node: Node = {
        uuid: 'test-node-uuid',
        actions: [
          {
            type: 'transfer_airtime',
            uuid: 'action-uuid',
            amounts: {
              USD: 10
            }
          } as TransferAirtime
        ],
        router: {
          type: 'switch',
          operand: '@locals._new_transfer',
          result_name: 'airtime_result',
          cases: [
            {
              uuid: 'case-1',
              type: 'has_text',
              arguments: [],
              category_uuid: 'cat-success'
            }
          ],
          categories: [
            { uuid: 'cat-success', name: 'Success', exit_uuid: 'exit-success' },
            { uuid: 'cat-failure', name: 'Failure', exit_uuid: 'exit-failure' }
          ],
          default_category_uuid: 'cat-failure'
        },
        exits: [
          { uuid: 'exit-success', destination_uuid: null },
          { uuid: 'exit-failure', destination_uuid: null }
        ]
      };

      const formData = split_by_airtime.toFormData!(node);
      expect(formData.result_name).to.equal('airtime_result');
    });

    it('should handle empty amounts', () => {
      const node: Node = {
        uuid: 'test-node-uuid',
        actions: [
          {
            type: 'transfer_airtime',
            uuid: 'action-uuid',
            amounts: {}
          } as TransferAirtime
        ],
        router: {
          type: 'switch',
          operand: '@locals._new_transfer',
          cases: [],
          categories: [
            { uuid: 'cat-failure', name: 'Failure', exit_uuid: 'exit-failure' }
          ],
          default_category_uuid: 'cat-failure'
        },
        exits: [{ uuid: 'exit-failure', destination_uuid: null }]
      };

      const formData = split_by_airtime.toFormData!(node);
      expect(formData.amounts).to.have.lengthOf(0);
    });
  });

  describe('fromFormData', () => {
    it('should create node with single currency from form data', () => {
      const originalNode: Node = {
        uuid: 'test-node-uuid',
        actions: [],
        exits: []
      };

      const formData = {
        uuid: 'test-node-uuid',
        amounts: [
          {
            currency: [{ value: 'USD', name: 'US Dollar (USD)' }],
            amount: '10'
          }
        ],
        result_name: ''
      };

      const node = split_by_airtime.fromFormData!(formData, originalNode);

      expect(node.uuid).to.equal('test-node-uuid');
      expect(node.actions).to.have.lengthOf(1);

      const action: any = node.actions![0];
      expect(action.type).to.equal('transfer_airtime');
      expect(action.amounts).to.deep.equal({ USD: 10 });

      expect(node.router?.type).to.equal('switch');
      expect(node.router?.categories).to.have.lengthOf(2);
      expect(node.router?.categories![0].name).to.equal('Success');
      expect(node.router?.categories![1].name).to.equal('Failure');
      expect(node.exits).to.have.lengthOf(2);
    });

    it('should create node with multiple currencies from form data', () => {
      const originalNode: Node = {
        uuid: 'test-node-uuid',
        actions: [],
        exits: []
      };

      const formData = {
        uuid: 'test-node-uuid',
        amounts: [
          {
            currency: [{ value: 'USD', name: 'US Dollar (USD)' }],
            amount: '10'
          },
          {
            currency: [{ value: 'EUR', name: 'Euro (EUR)' }],
            amount: '15.5'
          },
          {
            currency: [{ value: 'GBP', name: 'Pound Sterling (GBP)' }],
            amount: '8'
          }
        ],
        result_name: ''
      };

      const node = split_by_airtime.fromFormData!(formData, originalNode);

      expect(node.actions).to.have.lengthOf(1);

      const action: any = node.actions![0];
      expect(action.type).to.equal('transfer_airtime');
      expect(action.amounts).to.deep.equal({
        USD: 10,
        EUR: 15.5,
        GBP: 8
      });
    });

    it('should handle result_name in fromFormData', () => {
      const originalNode: Node = {
        uuid: 'test-node-uuid',
        actions: [],
        exits: []
      };

      const formData = {
        uuid: 'test-node-uuid',
        amounts: [
          {
            currency: [{ value: 'USD', name: 'US Dollar (USD)' }],
            amount: '10'
          }
        ],
        result_name: 'airtime_result'
      };

      const node = split_by_airtime.fromFormData!(formData, originalNode);
      expect(node.router?.result_name).to.equal('airtime_result');
    });

    it('should filter out empty amounts', () => {
      const originalNode: Node = {
        uuid: 'test-node-uuid',
        actions: [],
        exits: []
      };

      const formData = {
        uuid: 'test-node-uuid',
        amounts: [
          {
            currency: [{ value: 'USD', name: 'US Dollar (USD)' }],
            amount: '10'
          },
          {
            currency: [{ value: 'EUR', name: 'Euro (EUR)' }],
            amount: ''
          },
          {
            currency: null,
            amount: '5'
          }
        ],
        result_name: ''
      };

      const node = split_by_airtime.fromFormData!(formData, originalNode);

      const action: any = node.actions![0];
      expect(action.amounts).to.deep.equal({ USD: 10 });
    });

    it('should preserve existing action UUID', () => {
      const originalNode: Node = {
        uuid: 'test-node-uuid',
        actions: [
          {
            type: 'transfer_airtime',
            uuid: 'existing-action-uuid',
            amounts: { USD: 5 }
          } as TransferAirtime
        ],
        router: {
          type: 'switch',
          operand: '@locals._new_transfer',
          cases: [],
          categories: [],
          default_category_uuid: 'cat-1'
        },
        exits: []
      };

      const formData = {
        uuid: 'test-node-uuid',
        amounts: [
          {
            currency: [{ value: 'EUR', name: 'Euro (EUR)' }],
            amount: '20'
          }
        ],
        result_name: ''
      };

      const node = split_by_airtime.fromFormData!(formData, originalNode);

      const action: any = node.actions![0];
      expect(action.uuid).to.equal('existing-action-uuid');
    });

    it('should preserve existing category and exit UUIDs', () => {
      const originalNode: Node = {
        uuid: 'test-node-uuid',
        actions: [
          {
            type: 'transfer_airtime',
            uuid: 'action-uuid',
            amounts: { USD: 5 }
          } as TransferAirtime
        ],
        router: {
          type: 'switch',
          operand: '@locals._new_transfer',
          cases: [
            {
              uuid: 'case-1',
              type: 'has_text',
              arguments: [],
              category_uuid: 'cat-success'
            }
          ],
          categories: [
            { uuid: 'cat-success', name: 'Success', exit_uuid: 'exit-success' },
            { uuid: 'cat-failure', name: 'Failure', exit_uuid: 'exit-failure' }
          ],
          default_category_uuid: 'cat-failure'
        },
        exits: [
          { uuid: 'exit-success', destination_uuid: 'next-node-1' },
          { uuid: 'exit-failure', destination_uuid: 'next-node-2' }
        ]
      };

      const formData = {
        uuid: 'test-node-uuid',
        amounts: [
          {
            currency: [{ value: 'EUR', name: 'Euro (EUR)' }],
            amount: '20'
          }
        ],
        result_name: ''
      };

      const node = split_by_airtime.fromFormData!(formData, originalNode);

      // Check that UUIDs are preserved
      expect(node.router?.categories![0].uuid).to.equal('cat-success');
      expect(node.router?.categories![1].uuid).to.equal('cat-failure');
      expect(node.exits![0].uuid).to.equal('exit-success');
      expect(node.exits![1].uuid).to.equal('exit-failure');

      // Check that destinations are preserved
      expect(node.exits![0].destination_uuid).to.equal('next-node-1');
      expect(node.exits![1].destination_uuid).to.equal('next-node-2');
    });
  });

  describe('validate', () => {
    it('should validate when at least one valid amount is provided', () => {
      const formData = {
        amounts: [
          {
            currency: [{ value: 'USD', name: 'US Dollar (USD)' }],
            amount: '10'
          }
        ]
      };

      const result = split_by_airtime.validate!(formData);
      expect(result.valid).to.be.true;
      expect(Object.keys(result.errors)).to.have.lengthOf(0);
    });

    it('should fail validation when an amount exceeds the engine maximum', () => {
      const formData = {
        amounts: [
          {
            currency: [{ value: 'USD', name: 'US Dollar (USD)' }],
            amount: '2000000000000000'
          }
        ]
      };

      const result = split_by_airtime.validate!(formData);
      expect(result.valid).to.be.false;
      expect(result.errors.amounts).to.exist;
    });

    it('should validate an amount at the engine maximum', () => {
      const formData = {
        amounts: [
          {
            currency: [{ value: 'USD', name: 'US Dollar (USD)' }],
            amount: '1000000000000000'
          }
        ]
      };

      const result = split_by_airtime.validate!(formData);
      expect(result.valid).to.be.true;
    });

    it('should fail validation when no amounts are provided', () => {
      const formData = {
        amounts: []
      };

      const result = split_by_airtime.validate!(formData);
      expect(result.valid).to.be.false;
      expect(result.errors.amounts).to.exist;
    });

    it('should fail validation when amounts are empty', () => {
      const formData = {
        amounts: [
          {
            currency: [{ value: 'USD', name: 'US Dollar (USD)' }],
            amount: ''
          }
        ]
      };

      const result = split_by_airtime.validate!(formData);
      expect(result.valid).to.be.false;
      expect(result.errors.amounts).to.exist;
    });

    it('should fail validation when currency is not selected', () => {
      const formData = {
        amounts: [
          {
            currency: null,
            amount: '10'
          }
        ]
      };

      const result = split_by_airtime.validate!(formData);
      expect(result.valid).to.be.false;
      expect(result.errors.amounts).to.exist;
    });

    it('should fail validation for duplicate currencies', () => {
      const formData = {
        amounts: [
          {
            currency: [{ value: 'USD', name: 'US Dollar (USD)' }],
            amount: '10'
          },
          {
            currency: [{ value: 'USD', name: 'US Dollar (USD)' }],
            amount: '20'
          }
        ]
      };

      const result = split_by_airtime.validate!(formData);
      expect(result.valid).to.be.false;
      expect(result.errors.amounts).to.include('Duplicate');
    });

    it('should fail validation for non-numeric amounts', () => {
      const formData = {
        amounts: [
          {
            currency: [{ value: 'USD', name: 'US Dollar (USD)' }],
            amount: 'abc'
          }
        ]
      };

      const result = split_by_airtime.validate!(formData);
      expect(result.valid).to.be.false;
      expect(result.errors.amounts).to.include('valid positive numbers');
    });

    it('should fail validation for negative amounts', () => {
      const formData = {
        amounts: [
          {
            currency: [{ value: 'USD', name: 'US Dollar (USD)' }],
            amount: '-10'
          }
        ]
      };

      const result = split_by_airtime.validate!(formData);
      expect(result.valid).to.be.false;
      expect(result.errors.amounts).to.include('valid positive numbers');
    });

    it('should fail validation for zero amounts', () => {
      const formData = {
        amounts: [
          {
            currency: [{ value: 'USD', name: 'US Dollar (USD)' }],
            amount: '0'
          }
        ]
      };

      const result = split_by_airtime.validate!(formData);
      expect(result.valid).to.be.false;
      expect(result.errors.amounts).to.include('valid positive numbers');
    });

    it('should validate multiple valid amounts', () => {
      const formData = {
        amounts: [
          {
            currency: [{ value: 'USD', name: 'US Dollar (USD)' }],
            amount: '10'
          },
          {
            currency: [{ value: 'EUR', name: 'Euro (EUR)' }],
            amount: '15.5'
          }
        ]
      };

      const result = split_by_airtime.validate!(formData);
      expect(result.valid).to.be.true;
      expect(Object.keys(result.errors)).to.have.lengthOf(0);
    });
  });

  describe('render', () => {
    it('should render single currency', () => {
      const node: Node = {
        uuid: 'test-node-uuid',
        actions: [
          {
            type: 'transfer_airtime',
            uuid: 'action-uuid',
            amounts: {
              USD: 10
            }
          } as TransferAirtime
        ],
        exits: []
      };

      const result = split_by_airtime.render!(node);
      expect(result).to.exist;
    });

    it('should render multiple currencies', () => {
      const node: Node = {
        uuid: 'test-node-uuid',
        actions: [
          {
            type: 'transfer_airtime',
            uuid: 'action-uuid',
            amounts: {
              USD: 10,
              EUR: 15,
              GBP: 8
            }
          } as TransferAirtime
        ],
        exits: []
      };

      const result = split_by_airtime.render!(node);
      expect(result).to.exist;
    });

    it('should render placeholder when no amounts', () => {
      const node: Node = {
        uuid: 'test-node-uuid',
        actions: [
          {
            type: 'transfer_airtime',
            uuid: 'action-uuid',
            amounts: {}
          } as TransferAirtime
        ],
        exits: []
      };

      const result = split_by_airtime.render!(node);
      expect(result).to.exist;
    });
  });

  describe('round-trip conversion', () => {
    it('should maintain data through toFormData -> fromFormData cycle', () => {
      const originalNode: Node = {
        uuid: 'test-node-uuid',
        actions: [
          {
            type: 'transfer_airtime',
            uuid: 'action-uuid',
            amounts: {
              USD: 10,
              EUR: 15.5
            }
          } as TransferAirtime
        ],
        router: {
          type: 'switch',
          operand: '@locals._new_transfer',
          result_name: 'airtime_result',
          cases: [
            {
              uuid: 'case-1',
              type: 'has_text',
              arguments: [],
              category_uuid: 'cat-success'
            }
          ],
          categories: [
            { uuid: 'cat-success', name: 'Success', exit_uuid: 'exit-success' },
            { uuid: 'cat-failure', name: 'Failure', exit_uuid: 'exit-failure' }
          ],
          default_category_uuid: 'cat-failure'
        },
        exits: [
          { uuid: 'exit-success', destination_uuid: 'next-1' },
          { uuid: 'exit-failure', destination_uuid: 'next-2' }
        ]
      };

      // Convert to form data
      const formData = split_by_airtime.toFormData!(originalNode);

      // Convert back to node
      const resultNode = split_by_airtime.fromFormData!(formData, originalNode);

      // Check the action
      const action: any = resultNode.actions![0];
      expect(action.type).to.equal('transfer_airtime');
      expect(action.amounts).to.deep.equal({
        USD: 10,
        EUR: 15.5
      });

      // Check result_name is preserved
      expect(resultNode.router?.result_name).to.equal('airtime_result');

      // Check UUIDs are preserved
      expect(action.uuid).to.equal('action-uuid');
      expect(resultNode.router?.categories![0].uuid).to.equal('cat-success');
      expect(resultNode.router?.categories![1].uuid).to.equal('cat-failure');
    });
  });
});

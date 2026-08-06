import { expect } from '@open-wc/testing';
import { split_by_ticket } from '../src/flow/nodes/split_by_ticket';
import { set_contact_field } from '../src/flow/actions/set_contact_field';
import { set_contact_name } from '../src/flow/actions/set_contact_name';
import { send_msg } from '../src/flow/actions/send_msg';
import { wait_for_dial } from '../src/flow/nodes/wait_for_dial';

// these limits must match the validation caps enforced by the flow engine -
// without them the editor emits definitions the engine rejects at save time
describe('flow form config limits', () => {
  it('caps ticket note length', () => {
    expect((split_by_ticket.form.note as any).maxLength).to.equal(10000);
  });

  it('caps contact field value length', () => {
    expect((set_contact_field.form.value as any).maxLength).to.equal(10000);
  });

  it('caps contact name length', () => {
    expect((set_contact_name.form.name as any).maxLength).to.equal(1000);
  });

  it('caps attachment expression length', () => {
    const attachments = send_msg.form.runtime_attachments as any;
    expect(attachments.itemConfig.expression.maxLength).to.equal(8192);
  });

  it('caps dial phone length', () => {
    expect((wait_for_dial.form.phone as any).maxLength).to.equal(1000);
  });

  it('caps quick reply count and length', () => {
    const quickReplies = send_msg.form.quick_replies as any;
    expect(quickReplies.maxItems).to.equal(10);
    expect(quickReplies.maxLength).to.equal(1000);
  });
});

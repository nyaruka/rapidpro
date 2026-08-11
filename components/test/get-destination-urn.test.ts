import { expect } from '@open-wc/testing';
import { Contact } from '../src/interfaces';
import { getDestinationURN } from '../src/live/ContactStoreElement';

const contactWithURNs = (urns: any[]): Contact => {
  return { urns } as Contact;
};

describe('getDestinationURN', () => {
  it('returns the first URN with a channel', () => {
    const contact = contactWithURNs([
      { scheme: 'facebook', path: '123123', display: null, channel: null },
      {
        scheme: 'telegram',
        path: '24028613',
        display: 'dmb4ever',
        channel: { uuid: 'chan-2', name: 'Telegram Channel' }
      },
      {
        scheme: 'tel',
        path: '+12065553567',
        display: null,
        channel: { uuid: 'chan-3', name: 'SMS Channel' }
      }
    ]);

    expect(getDestinationURN(contact).scheme).to.equal('telegram');
  });

  it('returns null if no URNs are sendable', () => {
    const contact = contactWithURNs([
      { scheme: 'facebook', path: '123123', display: null, channel: null }
    ]);

    expect(getDestinationURN(contact)).to.be.null;
  });

  it('returns null for missing contact or URNs', () => {
    expect(getDestinationURN(null)).to.be.null;
    expect(getDestinationURN({} as Contact)).to.be.null;
    expect(getDestinationURN(contactWithURNs([]))).to.be.null;
  });
});

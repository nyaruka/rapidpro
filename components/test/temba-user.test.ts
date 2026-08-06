import '../temba-modules';
import { fixture, assert } from '@open-wc/testing';
import { TembaUser, getFullName } from '../src/display/TembaUser';

const createUser = async (markup: string): Promise<TembaUser> => {
  return (await fixture(markup)) as TembaUser;
};

describe('temba-user', () => {
  it('renders with initials from name', async () => {
    const user = await createUser('<temba-user name="Jane Doe"></temba-user>');
    assert.instanceOf(user, TembaUser);
    assert.equal(user.initials, 'JD');
    assert.notEqual(user.bgcolor, '#e6e6e6');
    assert.isNull(user.bgimage);
  });

  it('resets initials and bgcolor when name is cleared', async () => {
    const user = await createUser('<temba-user name="Jane Doe"></temba-user>');
    user.name = '';
    await user.updateComplete;
    assert.equal(user.initials, '');
    assert.equal(user.bgcolor, '#e6e6e6');
  });

  it('sets bgimage from avatar', async () => {
    const user = await createUser(
      '<temba-user name="Jane" avatar="/img/a.png"></temba-user>'
    );
    assert.include(user.bgimage, "url('/img/a.png')");
  });

  it('clears bgimage when avatar is removed', async () => {
    // lit reuses elements across renders, so an element that showed one
    // user's avatar must fall back to initials when reused for a user
    // without one
    const user = await createUser(
      '<temba-user name="Jane" avatar="/img/a.png"></temba-user>'
    );
    assert.include(user.bgimage, "url('/img/a.png')");

    user.avatar = null;
    user.name = 'Bob Contact';
    await user.updateComplete;
    assert.isNull(user.bgimage);
    assert.equal(user.initials, 'BC');
  });

  it('restores default avatar when avatar is removed from system user', async () => {
    const user = await createUser(
      '<temba-user name="Bot" system avatar="/img/a.png"></temba-user>'
    );
    assert.include(user.bgimage, "url('/img/a.png')");

    user.avatar = null;
    await user.updateComplete;
    assert.isNotNull(user.bgimage);
    assert.notInclude(user.bgimage, '/img/a.png');
  });

  it('uses default avatar when system is true', async () => {
    const user = await createUser(
      '<temba-user name="Bot" system></temba-user>'
    );
    assert.isNotNull(user.bgimage);
    assert.include(user.bgimage, 'url(');
  });

  it('renders the contact icon when there is no name or avatar', async () => {
    const user = await createUser('<temba-user></temba-user>');
    await user.updateComplete;
    assert.equal(user.initials, '');
    assert.isNull(user.bgimage);
    const icon = user.shadowRoot.querySelector('temba-icon');
    assert.isNotNull(icon);
    assert.equal(icon.getAttribute('name'), 'user-01');
  });

  it('does not render the contact icon when initials are present', async () => {
    const user = await createUser('<temba-user name="Jane Doe"></temba-user>');
    await user.updateComplete;
    assert.isNull(user.shadowRoot.querySelector('temba-icon'));
  });

  it('renders name when showName set', async () => {
    const user = await createUser(
      '<temba-user name="Jane Doe" showname scale="1"></temba-user>'
    );
    await user.updateComplete;
    const nameEl = user.shadowRoot.querySelector('.name');
    assert.isNotNull(nameEl);
    assert.include(nameEl.textContent, 'Jane Doe');
  });

  it('omits name element when showName is false', async () => {
    const user = await createUser('<temba-user name="Jane Doe"></temba-user>');
    await user.updateComplete;
    assert.isNull(user.shadowRoot.querySelector('.name'));
  });
});

describe('getFullName', () => {
  it('prefers first/last over name', () => {
    assert.equal(
      getFullName({ name: 'Jane', first_name: 'Jane', last_name: 'Doe' }),
      'Jane Doe'
    );
  });

  it('joins first and last when name is missing', () => {
    assert.equal(
      getFullName({ first_name: 'Jane', last_name: 'Doe' }),
      'Jane Doe'
    );
  });

  it('falls back to name when first/last are missing', () => {
    assert.equal(getFullName({ name: 'System' }), 'System');
  });

  it('handles missing last_name', () => {
    assert.equal(getFullName({ first_name: 'Jane' }), 'Jane');
  });
});

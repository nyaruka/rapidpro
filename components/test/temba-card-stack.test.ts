import { expect, fixture, oneEvent } from '@open-wc/testing';
import { html, TemplateResult } from 'lit';
import { CustomEventType } from '../src/interfaces';
import { CardStack } from '../src/layout/CardStack';
import { assertScreenshot, getClip } from './utils.test';
import Sinon, { useFakeTimers } from 'sinon';

const STACK = html`
  <temba-card-stack>
    <temba-card id="card-a" label="Alpha">
      <div style="height:30px">A</div>
    </temba-card>
    <temba-card id="card-b" label="Beta">
      <div style="height:30px">B</div>
    </temba-card>
    <temba-card id="card-c" label="Gamma">
      <div style="height:30px">C</div>
    </temba-card>
  </temba-card-stack>
`;

const createStack = async (def: TemplateResult) => {
  const parentNode = document.createElement('div');
  parentNode.setAttribute('style', 'width: 300px;');
  const stack = (await fixture(def, { parentNode })) as CardStack;
  await stack.updateComplete;
  return stack;
};

const getHeaderCenter = (stack: CardStack, id: string) => {
  const header = stack
    .querySelector(`#${id}`)
    .shadowRoot.querySelector('.card-header') as HTMLElement;
  const rect = header.getBoundingClientRect();
  return { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 };
};

describe('temba-card-stack', () => {
  let clock: Sinon.SinonFakeTimers;
  beforeEach(function () {
    clock = useFakeTimers();
    clock.runAll();
  });

  afterEach(function () {
    clock.restore();
  });

  it('renders and adds sortable class to children', async () => {
    const stack = await createStack(STACK);
    stack.querySelectorAll('temba-card').forEach((card) => {
      expect(card.classList.contains('sortable')).to.be.true;
    });
    expect(stack.getIds()).to.deep.equal(['card-a', 'card-b', 'card-c']);
    await assertScreenshot('layout/card-stack', getClip(stack));
  });

  it('applies an initial order attribute', async () => {
    const stack = await createStack(html`
      <temba-card-stack order='["card-c", "card-a"]'>
        <temba-card id="card-a" label="Alpha">
          <div>A</div>
        </temba-card>
        <temba-card id="card-b" label="Beta">
          <div>B</div>
        </temba-card>
        <temba-card id="card-c" label="Gamma">
          <div>C</div>
        </temba-card>
      </temba-card-stack>
    `);

    // listed ids first in given order, unlisted keep relative order after
    expect(stack.getIds()).to.deep.equal(['card-c', 'card-a', 'card-b']);
  });

  it('ignores unknown ids in the order attribute', async () => {
    const stack = await createStack(html`
      <temba-card-stack order='["card-x", "card-b"]'>
        <temba-card id="card-a" label="Alpha">
          <div>A</div>
        </temba-card>
        <temba-card id="card-b" label="Beta">
          <div>B</div>
        </temba-card>
      </temba-card-stack>
    `);

    expect(stack.getIds()).to.deep.equal(['card-b', 'card-a']);
  });

  it('reorders the DOM on drag and emits ids', async () => {
    const stack = await createStack(STACK);

    const from = getHeaderCenter(stack, 'card-a');
    const orderChanged = oneEvent(stack, CustomEventType.OrderChanged, false);

    // drag card-a's header below card-c
    await moveMouse(from.x, from.y);
    await mouseDown();
    const stackBounds = stack.getBoundingClientRect();
    await moveMouse(from.x, stackBounds.bottom - 5);

    // mid-drag the ghost mirrors the dragged card — an open card drags
    // open, with its content along for the ride
    const ghost = document.body.querySelector(
      'temba-card.ghost'
    ) as HTMLElement;
    expect(ghost).to.exist;
    expect(ghost.hasAttribute('collapsed')).to.be.false;
    expect(ghost.children.length).to.be.greaterThan(0);
    expect(ghost.hasAttribute('id')).to.be.false;

    await mouseUp();
    clock.runAll();

    const event = await orderChanged;
    expect(event.detail.ids).to.deep.equal(['card-b', 'card-c', 'card-a']);
    expect(stack.getIds()).to.deep.equal(['card-b', 'card-c', 'card-a']);

    // light DOM order actually changed
    const domIds = Array.from(stack.querySelectorAll('temba-card')).map(
      (card) => card.id
    );
    expect(domIds).to.deep.equal(['card-b', 'card-c', 'card-a']);
  });

  it('starts a drag from the grip icon', async () => {
    const stack = await createStack(STACK);

    const grip = stack
      .querySelector('#card-a')
      .shadowRoot.querySelector('.grip') as HTMLElement;
    const rect = grip.getBoundingClientRect();
    const stackBounds = stack.getBoundingClientRect();

    const orderChanged = oneEvent(stack, CustomEventType.OrderChanged, false);

    await moveMouse(rect.left + rect.width / 2, rect.top + rect.height / 2);
    await mouseDown();
    await moveMouse(rect.left + rect.width / 2, stackBounds.bottom - 5);
    await mouseUp();
    clock.runAll();

    const event = await orderChanged;
    expect(event.detail.ids).to.deep.equal(['card-b', 'card-c', 'card-a']);
  });

  it('does not start a drag from the card body', async () => {
    const stack = await createStack(STACK);

    const body = stack.querySelector('#card-a div') as HTMLElement;
    const rect = body.getBoundingClientRect();

    await moveMouse(rect.left + 10, rect.top + 10);
    await mouseDown();
    const stackBounds = stack.getBoundingClientRect();
    await moveMouse(rect.left + 10, stackBounds.bottom - 5);
    await mouseUp();
    clock.runAll();

    expect(stack.getIds()).to.deep.equal(['card-a', 'card-b', 'card-c']);
  });
});

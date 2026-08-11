import { fixture, expect, assert } from '@open-wc/testing';
import {
  SampleMedia,
  setSampleMedia,
  Simulator
} from '../src/simulator/Simulator';
import { getCookie, setCookie } from '../src/utils';
import {
  assertScreenshot,
  getClip,
  mockPOST,
  clearMockPosts,
  delay,
  waitForCondition,
  waitForImages,
  loadStore
} from './utils.test';
import { zustand } from '../src/store/AppState';

const FLOW_UUID = 'test-flow-123';

const createSimulator = async (attrs: any = {}) => {
  // load store first since simulator depends on it
  await loadStore();

  const defaults = {
    flow: FLOW_UUID,
    animationTime: '0' // disable animations for deterministic tests
  };
  const mergedAttrs = { ...defaults, ...attrs };

  const attrString = Object.entries(mergedAttrs)
    .map(([key, value]) => `${key}="${value}"`)
    .join(' ');

  const simulator: Simulator = await fixture(
    `<temba-simulator ${attrString}></temba-simulator>`
  );

  // reset cookie-based properties for deterministic tests
  simulator.size = 'medium';
  (simulator as any).following = true;
  (simulator as any).contextExplorerOpen = false;
  await simulator.updateComplete;

  return simulator;
};

// create simulator without overriding cookie-restored properties.
// `cookieValue` (when provided) is written to the simulator cookie immediately
// before the fixture is created, so it can't be clobbered by anything that
// happens during the async loadStore() above (e.g. a stray updated() from a
// previous test's element).
const createSimulatorRaw = async (attrs: any = {}, cookieValue?: string) => {
  await loadStore();

  if (cookieValue !== undefined) {
    setCookie('simulator', cookieValue);
  }

  const defaults = {
    flow: FLOW_UUID,
    animationTime: '0'
  };
  const mergedAttrs = { ...defaults, ...attrs };

  const attrString = Object.entries(mergedAttrs)
    .map(([key, value]) => `${key}="${value}"`)
    .join(' ');

  const simulator: Simulator = await fixture(
    `<temba-simulator ${attrString}></temba-simulator>`
  );
  await simulator.updateComplete;
  return simulator;
};

// helper to open the simulator
const openSimulator = async (simulator: Simulator) => {
  const tab = simulator.shadowRoot.querySelector('temba-floating-tab') as any;
  expect(tab).to.exist;

  // trigger the button clicked event on the tab
  tab.dispatchEvent(new CustomEvent('temba-button-clicked', { bubbles: true }));

  await simulator.updateComplete;
  // brief delay for async API response processing
  await delay(50);
};

// helper to get clip for the simulator window (fixed positioning)
const getSimulatorClip = (
  simulator: Simulator,
  includeContext: boolean = false
) => {
  const phoneWindow = simulator.shadowRoot.querySelector(
    'temba-floating-window'
  ) as any;

  if (!phoneWindow) {
    // if window not open, use default clip
    return getClip(simulator);
  }

  const windowElement = phoneWindow.shadowRoot?.querySelector(
    '.window'
  ) as HTMLElement;
  if (!windowElement) {
    return getClip(simulator);
  }

  const windowBounds = windowElement.getBoundingClientRect();

  if (includeContext) {
    // get the context explorer and phone to clip just those areas
    const phoneSimulator = phoneWindow.querySelector(
      '.phone-simulator'
    ) as HTMLElement;
    if (!phoneSimulator) {
      return getClip(simulator);
    }

    const contextExplorer = phoneSimulator.querySelector(
      '.context-explorer'
    ) as HTMLElement;
    const phoneFrame = phoneSimulator.querySelector(
      '.phone-frame'
    ) as HTMLElement;

    if (!contextExplorer || !phoneFrame) {
      return {
        x: windowBounds.x,
        y: windowBounds.y,
        width: windowBounds.width,
        height: windowBounds.height
      };
    }

    const contextBounds = contextExplorer.getBoundingClientRect();
    const phoneBounds = phoneFrame.getBoundingClientRect();

    // clip from the left edge of context explorer to the right edge of phone frame only
    // do not include the option-pane which is to the right of the phone
    // keep padding within the phone bounds to avoid capturing the gap to the option pane
    const padding = 10;
    const leftX = contextBounds.x - padding;

    // don't extend past the phone frame right edge - the option pane is close by
    const rightX = phoneBounds.right;

    const topY = Math.min(contextBounds.y, phoneBounds.y) - padding;
    const bottomY =
      Math.max(contextBounds.bottom, phoneBounds.bottom) + padding;

    return {
      x: leftX,
      y: topY,
      width: rightX - leftX,
      height: bottomY - topY
    };
  }

  // the phone-simulator is in the light DOM of the phoneWindow (slotted content)
  const phoneSimulator = phoneWindow.querySelector(
    '.phone-simulator'
  ) as HTMLElement;
  if (!phoneSimulator) {
    return getClip(simulator);
  }

  // get the phone-frame from within the phone-simulator
  const phoneFrame = phoneSimulator.querySelector(
    '.phone-frame'
  ) as HTMLElement;
  if (!phoneFrame) {
    // fallback to window bounds if phone-frame not found
    return {
      x: windowBounds.x,
      y: windowBounds.y,
      width: windowBounds.width,
      height: windowBounds.height
    };
  }

  const frameBounds = phoneFrame.getBoundingClientRect();

  // clip to just the phone frame area
  const padding = 10;

  return {
    x: frameBounds.x - padding,
    y: frameBounds.y - padding,
    // only add padding to the left to avoid capturing option pane on right
    width: frameBounds.width + padding,
    height: frameBounds.height + padding * 2
  };
};

// helper to get message count from chat component
const getMessageCount = (simulator: Simulator): number => {
  const chat = simulator.shadowRoot.querySelector('temba-chat') as any;
  if (!chat) {
    return 0;
  }
  // check how many messages are in the chat component
  // the chat component stores messages in its internal state
  return (
    chat.messageGroups?.reduce((total: number, group: any) => {
      return total + (group.messages?.length || 0);
    }, 0) || 0
  );
};

// the chat component renders messages asynchronously (batched via setTimeout),
// so poll rather than counting immediately after opening the simulator
const waitForMessages = async (simulator: Simulator, minCount: number = 1) => {
  await waitForCondition(() => getMessageCount(simulator) >= minCount, 40, 50);
};

// mock responses for simulation endpoints
const mockSimulatorStart = () => {
  const response = {
    session: {
      status: 'waiting',
      trigger: {
        type: 'manual',
        flow: { uuid: FLOW_UUID, name: 'Test Flow' }
      },
      runs: [
        {
          uuid: 'run-1',
          flow: { uuid: FLOW_UUID, name: 'Test Flow' },
          status: 'waiting',
          path: [
            {
              uuid: 'step-1',
              node_uuid: 'node-1',
              arrived_on: new Date().toISOString(),
              exit_uuid: null
            }
          ]
        }
      ],
      environment: {
        date_format: 'YYYY-MM-DD',
        time_format: 'HH:mm',
        timezone: 'America/New_York',
        allowed_languages: ['eng'],
        default_country: 'US'
      }
    },
    events: [
      {
        type: 'msg_created',
        created_on: new Date().toISOString(),
        msg: {
          uuid: 'msg-1',
          text: 'Hello! How can I help you today?',
          urn: 'tel:+12065551212'
        }
      }
    ],
    contact: {
      uuid: 'fb3787ab-2eda-48a0-a2bc-e2ddadec1286',
      urns: ['tel:+12065551212'],
      fields: {},
      groups: [],
      language: 'eng',
      status: 'active',
      created_on: new Date().toISOString()
    },
    context: {
      contact: {
        uuid: 'fb3787ab-2eda-48a0-a2bc-e2ddadec1286',
        name: 'Test User',
        urns: {
          tel: ['+12065551212'],
          __default__: '+12065551212'
        },
        fields: {
          age: '25',
          city: 'Seattle'
        }
      },
      trigger: {
        type: 'manual',
        __default__: 'manual'
      }
    }
  };

  mockPOST(/\/flow\/simulate\/.*\//, response);
};

const mockSimulatorResume = (responseText: string, quickReplies?: string[]) => {
  const msg: any = {
    uuid: 'msg-response',
    text: responseText,
    urn: 'tel:+12065551212'
  };

  if (quickReplies) {
    msg.quick_replies = quickReplies.map((text) => ({ text }));
  }

  const response = {
    session: {
      status: 'waiting',
      trigger: {
        type: 'manual',
        flow: { uuid: FLOW_UUID, name: 'Test Flow' }
      },
      runs: [
        {
          uuid: 'run-1',
          flow: { uuid: FLOW_UUID, name: 'Test Flow' },
          status: 'waiting',
          path: [
            {
              uuid: 'step-1',
              node_uuid: 'node-1',
              arrived_on: new Date().toISOString(),
              exit_uuid: 'exit-1'
            },
            {
              uuid: 'step-2',
              node_uuid: 'node-2',
              arrived_on: new Date().toISOString(),
              exit_uuid: null
            }
          ]
        }
      ],
      environment: {
        date_format: 'YYYY-MM-DD',
        time_format: 'HH:mm',
        timezone: 'America/New_York',
        allowed_languages: ['eng'],
        default_country: 'US'
      }
    },
    events: [
      {
        type: 'msg_created',
        created_on: new Date().toISOString(),
        msg
      }
    ],
    contact: {
      uuid: 'fb3787ab-2eda-48a0-a2bc-e2ddadec1286',
      urns: ['tel:+12065551212'],
      fields: {
        age: '25',
        city: 'Seattle'
      },
      groups: [],
      language: 'eng',
      status: 'active',
      created_on: new Date().toISOString()
    },
    context: {
      contact: {
        uuid: 'fb3787ab-2eda-48a0-a2bc-e2ddadec1286',
        name: 'Test User',
        urns: {
          tel: ['+12065551212'],
          __default__: '+12065551212'
        },
        fields: {
          age: '25',
          city: 'Seattle'
        }
      },
      results: {
        user_response: {
          value: responseText,
          __default__: responseText
        }
      }
    }
  };

  mockPOST(/\/flow\/simulate\/.*\//, response);
};

describe('temba-simulator', () => {
  beforeEach(() => {
    clearMockPosts();
  });

  afterEach(() => {
    // ensure flushSave is always cleaned up to prevent cascade failures
    zustand.getState().setFlushSave(null);
  });

  it('can be created', async () => {
    const simulator: Simulator = await createSimulator();
    assert.instanceOf(simulator, Simulator);
    expect(simulator.flow).to.equal(FLOW_UUID);
    expect(simulator.endpoint).to.equal(`/flow/simulate/${FLOW_UUID}/`);
  });

  it('opens simulator window and starts flow', async () => {
    mockSimulatorStart();

    const simulator: Simulator = await createSimulator();
    await simulator.updateComplete;
    await openSimulator(simulator);

    const phoneWindow = simulator.shadowRoot.querySelector(
      'temba-floating-window'
    ) as any;
    expect(phoneWindow).to.exist;

    // verify phone screen is visible
    const phoneScreen = simulator.shadowRoot.querySelector('.phone-screen');
    expect(phoneScreen).to.exist;

    // verify initial message is displayed via chat component
    await waitForMessages(simulator);
    const messageCount = getMessageCount(simulator);
    expect(messageCount).to.be.greaterThan(0);

    await assertScreenshot(
      'simulator/open-initial',
      getSimulatorClip(simulator)
    );
  });

  it('sends a text message', async () => {
    mockSimulatorStart();

    const simulator: Simulator = await createSimulator();
    await simulator.updateComplete;
    await openSimulator(simulator);

    // count initial messages once the initial message has rendered
    await waitForMessages(simulator);
    const initialCount = getMessageCount(simulator);

    // mock the resume response
    mockSimulatorResume('Thanks for your message!');

    // type a message
    const input = simulator.shadowRoot.querySelector(
      '.message-input input'
    ) as HTMLInputElement;
    expect(input).to.exist;

    input.value = 'Hello from test';
    input.dispatchEvent(new Event('input'));
    await simulator.updateComplete;

    // press enter to send
    const enterEvent = new KeyboardEvent('keyup', {
      key: 'Enter',
      bubbles: true
    });
    input.dispatchEvent(enterEvent);

    // wait for the message to be sent and response to come back
    await waitForCondition(
      () => getMessageCount(simulator) > initialCount,
      40,
      50
    );

    await simulator.updateComplete;
    // wait for chat component to update
    const chat = simulator.shadowRoot.querySelector('temba-chat') as any;
    if (chat) {
      await chat.updateComplete;
    }

    // verify we have more messages than before
    const newCount = getMessageCount(simulator);
    expect(newCount).to.be.greaterThan(initialCount);
  });

  it('tests message flow and takes screenshot', async () => {
    mockSimulatorStart();

    const simulator: Simulator = await createSimulator();
    await simulator.updateComplete;
    await openSimulator(simulator);

    // clear previous mocks and set up new mock for a response
    clearMockPosts();
    mockSimulatorResume('Thank you for your message!', ['Yes', 'No', 'Maybe']);

    // send a message
    const input = simulator.shadowRoot.querySelector(
      '.message-input input'
    ) as HTMLInputElement;
    input.value = 'Test message';
    input.dispatchEvent(new Event('input'));

    const enterEvent = new KeyboardEvent('keyup', {
      key: 'Enter',
      bubbles: true
    });
    input.dispatchEvent(enterEvent);

    // wait for quick replies to appear
    await waitForCondition(
      () =>
        simulator.shadowRoot.querySelectorAll('.quick-reply-btn').length > 0,
      5000
    );
    await simulator.updateComplete;
    await delay(100); // extra delay for rendering

    // take screenshot with quick replies
    await assertScreenshot(
      'simulator/quick-replies',
      getSimulatorClip(simulator),
      true
    );
  });

  it('opens attachment menu', async () => {
    mockSimulatorStart();

    const simulator: Simulator = await createSimulator();
    await simulator.updateComplete;
    await openSimulator(simulator);

    // click the attachment button
    const attachmentButton = simulator.shadowRoot.querySelector(
      '.attachment-button'
    ) as HTMLElement;
    expect(attachmentButton).to.exist;
    attachmentButton.click();

    await simulator.updateComplete;

    // verify attachment menu is displayed
    const attachmentMenu =
      simulator.shadowRoot.querySelector('.attachment-menu');
    expect(attachmentMenu).to.exist;
    expect(attachmentMenu.classList.contains('open')).to.be.true;

    await assertScreenshot(
      'simulator/attachment-menu',
      getSimulatorClip(simulator),
      true
    );
  });

  it('sends an image attachment', async () => {
    // the simulator's own samples are hosted on s3 - point at a local copy of
    // the same image so this doesn't turn a screenshot comparison into a
    // check that a third party is reachable and quick
    let previousSamples: SampleMedia = null;
    try {
      previousSamples = setSampleMedia({
        images: ['/test-assets/img/sim_image_c.jpg']
      });
      await sendImageAttachment();
    } finally {
      if (previousSamples) {
        setSampleMedia(previousSamples);
      }
    }
  });

  const sendImageAttachment = async () => {
    mockSimulatorStart();

    const simulator: Simulator = await createSimulator();
    await simulator.updateComplete;
    // reset attachment indices for deterministic testing
    simulator.resetAttachmentIndices();
    await openSimulator(simulator);

    // count initial messages once the initial message has rendered
    await waitForMessages(simulator);
    const initialCount = getMessageCount(simulator);

    // mock the response for image attachment
    mockSimulatorResume('Nice picture!');

    // open attachment menu and click image option
    const attachmentButton = simulator.shadowRoot.querySelector(
      '.attachment-button'
    ) as HTMLElement;
    attachmentButton.click();
    await simulator.updateComplete;
    await delay(200);

    const imageMenuItem = Array.from(
      simulator.shadowRoot.querySelectorAll('.attachment-menu-item')
    ).find((el) => el.textContent?.includes('Image')) as HTMLElement;
    expect(imageMenuItem).to.exist;
    imageMenuItem.click();

    // wait for the attachment to be sent and response to come back
    await waitForCondition(
      () => getMessageCount(simulator) > initialCount,
      40,
      50
    );

    await simulator.updateComplete;
    // wait for chat component to update
    const chat = simulator.shadowRoot.querySelector('temba-chat') as any;
    if (chat) {
      await chat.updateComplete;
    }

    // verify message with attachment was added via chat component
    const newCount = getMessageCount(simulator);
    expect(newCount).to.be.greaterThan(initialCount);

    // still a fetch, just a local one - the shot has to wait for it or it
    // captures the empty box where the image lands
    await waitForImages(simulator.shadowRoot);
    await assertScreenshot(
      'simulator/image-attachment',
      getSimulatorClip(simulator),
      true
    );
  };

  it('opens context explorer', async () => {
    mockSimulatorStart();

    const simulator: Simulator = await createSimulator();
    await openSimulator(simulator);

    // find and click the context explorer button (has expressions icon)
    const optionButtons = Array.from(
      simulator.shadowRoot.querySelectorAll('.option-btn')
    );
    const contextButton = optionButtons.find((btn) =>
      btn.querySelector('temba-icon[name="expressions"]')
    ) as HTMLElement;
    expect(contextButton).to.exist;
    contextButton.click();

    await simulator.updateComplete;
    await delay(100);

    // verify context explorer is displayed
    const contextExplorer =
      simulator.shadowRoot.querySelector('.context-explorer');
    expect(contextExplorer).to.exist;
    expect(contextExplorer.classList.contains('open')).to.be.true;

    // delay for context explorer to fully render
    await delay(300);
    await simulator.updateComplete;
    await document.fonts.ready;

    await assertScreenshot(
      'simulator/context-explorer-open',
      getSimulatorClip(simulator, true)
    );
  });

  it('expands context tree items', async () => {
    mockSimulatorStart();

    const simulator: Simulator = await createSimulator();
    await openSimulator(simulator);

    // ensure context explorer starts closed
    if ((simulator as any).contextExplorerOpen) {
      // click to close it first
      const optionButtons = Array.from(
        simulator.shadowRoot.querySelectorAll('.option-btn')
      );
      const contextButton = optionButtons.find((btn) =>
        btn.querySelector('temba-icon[name="expressions"]')
      ) as HTMLElement;
      contextButton.click();
      await simulator.updateComplete;
      await delay(100);
    }

    // now open context explorer
    const optionButtons = Array.from(
      simulator.shadowRoot.querySelectorAll('.option-btn')
    );
    const contextButton = optionButtons.find((btn) =>
      btn.querySelector('temba-icon[name="expressions"]')
    ) as HTMLElement;
    expect(contextButton).to.exist;
    contextButton.click();

    await simulator.updateComplete;
    await delay(100);

    // verify context explorer is now open
    expect((simulator as any).contextExplorerOpen).to.be.true;
    const contextExplorer =
      simulator.shadowRoot.querySelector('.context-explorer');
    expect(contextExplorer).to.exist;
    expect(contextExplorer.classList.contains('open')).to.be.true;

    // find and click on an expandable item (should have context-item-expandable class)
    const expandableItems = simulator.shadowRoot.querySelectorAll(
      '.context-item-expandable'
    );
    expect(expandableItems.length).to.be.greaterThan(0);

    const firstExpandable = expandableItems[0] as HTMLElement;
    firstExpandable.click();

    // wait for children to be displayed with specific content
    await waitForCondition(() => {
      const children =
        simulator.shadowRoot.querySelectorAll('.context-children');
      if (children.length === 0) return false;
      // also check that the children have rendered content
      const items = simulator.shadowRoot.querySelectorAll('.context-item');
      return items.length > expandableItems.length;
    }, 2000);

    // verify children are displayed
    const contextChildren =
      simulator.shadowRoot.querySelectorAll('.context-children');
    expect(contextChildren.length).to.be.greaterThan(0);

    await simulator.updateComplete;
    // delay for DOM to fully render expanded content (context rendering is complex)
    await delay(300);
    await simulator.updateComplete;

    // ensure fonts are loaded and give extra time for rendering
    await document.fonts.ready;

    // wait for any pending animation frames
    await new Promise((resolve) =>
      requestAnimationFrame(() => requestAnimationFrame(resolve))
    );
    await delay(200);

    await assertScreenshot(
      'simulator/context-expanded',
      getSimulatorClip(simulator, true)
    );
  });

  it('cycles simulator size', async () => {
    mockSimulatorStart();

    const simulator: Simulator = await createSimulator();
    await openSimulator(simulator);

    // initially should be medium (set in createSimulator)
    expect(simulator.size).to.equal('medium');

    // find and click the size button (shows current size as text)
    const optionButtons = Array.from(
      simulator.shadowRoot.querySelectorAll('.option-btn')
    );
    const sizeButton = optionButtons.find((btn) => {
      const text = btn.textContent?.trim();
      return text === 'S' || text === 'M' || text === 'L';
    }) as HTMLElement;
    expect(sizeButton).to.exist;
    sizeButton.click();

    await simulator.updateComplete;

    // should now be large (medium -> large)
    expect(simulator.size).to.equal('large');
  });

  it('resets simulation', async () => {
    mockSimulatorStart();

    const simulator: Simulator = await createSimulator();
    await simulator.updateComplete;
    await openSimulator(simulator);

    // wait for the initial message to render before sending
    await waitForMessages(simulator);

    // send a message first
    mockSimulatorResume('Response to test message');
    const input = simulator.shadowRoot.querySelector(
      '.message-input input'
    ) as HTMLInputElement;
    input.value = 'Test message';
    input.dispatchEvent(new Event('input'));

    const enterEvent = new KeyboardEvent('keyup', {
      key: 'Enter',
      bubbles: true
    });
    input.dispatchEvent(enterEvent);

    // wait for the sent message and response to render
    await waitForMessages(simulator, 2);
    await simulator.updateComplete;

    // verify we have multiple messages
    const messageCountBefore = getMessageCount(simulator);
    expect(messageCountBefore).to.be.greaterThan(1);

    // mock the start response for reset
    mockSimulatorStart();

    // click the reset button (has refresh icon)
    const optionButtons = Array.from(
      simulator.shadowRoot.querySelectorAll('.option-btn')
    );
    const resetButton = optionButtons.find((btn) =>
      btn.querySelector('temba-icon[name="reset"]')
    ) as HTMLElement;
    expect(resetButton).to.exist;
    resetButton.click();

    // wait for the chat to be cleared and the initial message to re-render —
    // the restarted flow has exactly one message, so anything more is a
    // leftover from the pre-reset chat still mid-teardown
    await waitForCondition(() => getMessageCount(simulator) === 1, 40, 50);
    await simulator.updateComplete;

    // a stale sprint reply from before the reset must not sneak back in —
    // give the (discarded) 400ms typing delay time to fire before comparing
    await delay(600);
    expect(getMessageCount(simulator)).to.equal(1);

    // verify messages are reset - should go back to just initial message
    const messageCountAfter = getMessageCount(simulator);
    expect(messageCountAfter).to.be.lessThan(messageCountBefore);

    await assertScreenshot(
      'simulator/after-reset',
      getSimulatorClip(simulator)
    );
  });

  it('flushes pending saves before starting simulation', async () => {
    let flushResolved = false;
    let flushCalled = false;

    mockSimulatorStart();

    const simulator: Simulator = await createSimulator();
    await simulator.updateComplete;

    // register a flushSave after the store is loaded but before opening
    zustand.getState().setFlushSave(() => {
      flushCalled = true;
      return new Promise<void>((resolve) => {
        setTimeout(() => {
          flushResolved = true;
          resolve();
        }, 100);
      });
    });

    // open the simulator — this triggers handleShow which calls flushSave
    const tab = simulator.shadowRoot.querySelector('temba-floating-tab') as any;
    tab.dispatchEvent(
      new CustomEvent('temba-button-clicked', { bubbles: true })
    );
    await simulator.updateComplete;
    await delay(200);

    // flushSave should have been called and resolved before startFlow
    expect(flushCalled).to.be.true;
    expect(flushResolved).to.be.true;

    // clean up
    zustand.getState().setFlushSave(null);
  });

  it('flushes pending saves before resetting simulation', async () => {
    mockSimulatorStart();

    const simulator: Simulator = await createSimulator();
    await simulator.updateComplete;
    await openSimulator(simulator);

    await delay(100);
    await simulator.updateComplete;

    // now register a flushSave we control for the reset path
    let flushResolved = false;
    let flushCalled = false;

    zustand.getState().setFlushSave(() => {
      flushCalled = true;
      return new Promise<void>((resolve) => {
        setTimeout(() => {
          flushResolved = true;
          resolve();
        }, 100);
      });
    });

    // mock the start response for reset
    mockSimulatorStart();

    // click the reset button
    const optionButtons = Array.from(
      simulator.shadowRoot.querySelectorAll('.option-btn')
    );
    const resetButton = optionButtons.find((btn) =>
      btn.querySelector('temba-icon[name="reset"]')
    ) as HTMLElement;
    expect(resetButton).to.exist;
    resetButton.click();

    await delay(200);
    await simulator.updateComplete;

    // flushSave should have been called and resolved before startFlow
    expect(flushCalled).to.be.true;
    expect(flushResolved).to.be.true;

    // clean up
    zustand.getState().setFlushSave(null);
  });

  it('displays event info messages', async () => {
    const responseWithEvents = {
      session: {
        status: 'waiting',
        trigger: {
          type: 'manual',
          flow: { uuid: FLOW_UUID, name: 'Test Flow' }
        },
        runs: [
          {
            uuid: 'run-1',
            flow: { uuid: FLOW_UUID, name: 'Test Flow' },
            status: 'waiting',
            path: [
              {
                uuid: 'step-1',
                node_uuid: 'node-1',
                arrived_on: new Date().toISOString(),
                exit_uuid: null
              }
            ]
          }
        ],
        environment: {
          date_format: 'YYYY-MM-DD',
          time_format: 'HH:mm',
          timezone: 'America/New_York',
          allowed_languages: ['eng'],
          default_country: 'US'
        }
      },
      events: [
        {
          type: 'contact_field_changed',
          created_on: new Date().toISOString(),
          field: { key: 'name', name: 'Name' },
          value: { text: 'John Doe' }
        },
        {
          type: 'msg_created',
          created_on: new Date().toISOString(),
          msg: {
            uuid: 'msg-1',
            text: 'Your name has been updated!',
            urn: 'tel:+12065551212'
          }
        }
      ],
      contact: {
        uuid: 'fb3787ab-2eda-48a0-a2bc-e2ddadec1286',
        urns: ['tel:+12065551212'],
        fields: {
          name: 'John Doe'
        },
        groups: [],
        language: 'eng',
        status: 'active',
        created_on: new Date().toISOString()
      },
      context: {
        contact: {
          uuid: 'fb3787ab-2eda-48a0-a2bc-e2ddadec1286',
          name: 'John Doe',
          fields: {
            name: 'John Doe'
          }
        }
      }
    };

    mockPOST(/\/flow\/simulate\/.*\//, responseWithEvents);

    const simulator: Simulator = await createSimulator();
    await simulator.updateComplete;
    await openSimulator(simulator);

    // verify events are displayed via chat component (field change + message = 2 events)
    await waitForMessages(simulator);
    const messageCount = getMessageCount(simulator);
    expect(messageCount).to.be.greaterThan(0);

    await assertScreenshot('simulator/event-info', getSimulatorClip(simulator));
  });

  it('opens webhook call details dialog from webhook events', async () => {
    const responseWithWebhookEvent = {
      session: {
        status: 'waiting',
        trigger: {
          type: 'manual',
          flow: { uuid: FLOW_UUID, name: 'Test Flow' }
        },
        runs: [
          {
            uuid: 'run-1',
            flow: { uuid: FLOW_UUID, name: 'Test Flow' },
            status: 'waiting',
            path: [
              {
                uuid: 'step-1',
                node_uuid: 'node-1',
                arrived_on: new Date().toISOString(),
                exit_uuid: null
              }
            ]
          }
        ],
        environment: {
          date_format: 'YYYY-MM-DD',
          time_format: 'HH:mm',
          timezone: 'America/New_York',
          allowed_languages: ['eng'],
          default_country: 'US'
        }
      },
      events: [
        {
          type: 'webhook_called',
          created_on: new Date().toISOString(),
          url: 'https://example.org/hooks/lead',
          status: 'success',
          status_code: 200,
          elapsed_ms: 150,
          request: {
            contact: { name: 'Alice', urn: 'tel:+12065551212' },
            payload: { source: 'simulator' }
          },
          response: {
            ok: true,
            id: 'response-1'
          }
        }
      ],
      contact: {
        uuid: 'fb3787ab-2eda-48a0-a2bc-e2ddadec1286',
        urns: ['tel:+12065551212'],
        fields: {},
        groups: [],
        language: 'eng',
        status: 'active',
        created_on: new Date().toISOString()
      },
      context: {
        contact: {
          uuid: 'fb3787ab-2eda-48a0-a2bc-e2ddadec1286',
          name: 'Alice'
        }
      }
    };

    mockPOST(/\/flow\/simulate\/.*\//, responseWithWebhookEvent);

    const simulator: Simulator = await createSimulator();
    await simulator.updateComplete;
    await openSimulator(simulator);

    const chat = simulator.shadowRoot.querySelector('temba-chat') as any;
    expect(chat).to.exist;
    await chat.updateComplete;

    // the webhook event starts collapsed behind a summary pill —
    // expand it to get at the details button
    await waitForCondition(
      () =>
        !!chat.shadowRoot?.querySelector('temba-label[title="Show details"]'),
      40,
      50
    );
    (
      chat.shadowRoot.querySelector(
        'temba-label[title="Show details"]'
      ) as HTMLElement
    ).click();
    await chat.updateComplete;

    await waitForCondition(
      () => !!chat.shadowRoot?.querySelector('[data-webhook-details]'),
      40,
      50
    );

    const webhookDetailsButton = chat.shadowRoot.querySelector(
      '[data-webhook-details]'
    ) as HTMLElement;
    expect(webhookDetailsButton).to.exist;
    webhookDetailsButton.click();

    await simulator.updateComplete;
    await waitForCondition(
      () =>
        !!simulator.shadowRoot.querySelector('temba-dialog') &&
        (simulator.shadowRoot.querySelector('temba-dialog') as any).open,
      40,
      50
    );

    const dialog = simulator.shadowRoot.querySelector('temba-dialog') as any;
    expect(dialog).to.exist;
    expect(dialog.open).to.be.true;

    const detailsText = dialog.textContent || '';
    expect(detailsText).to.match(/1\s+attempt/);
    expect(detailsText).to.contain('150 ms total elapsed');
    expect(detailsText).to.not.contain('Attempt 1');
    expect(detailsText).to.contain('"name": "Alice"');
    expect(detailsText).to.contain('"ok": true');
  });

  it('formats minute-boundary webhook durations correctly', async () => {
    const simulator: Simulator = await createSimulator();
    expect((simulator as any).formatWebhookDuration(119999)).to.equal('2m 0s');
  });

  it('aggregates webhook elapsed totals for multiple duration formats', async () => {
    const responseWithWebhookEvent = {
      session: {
        status: 'waiting',
        trigger: {
          type: 'manual',
          flow: { uuid: FLOW_UUID, name: 'Test Flow' }
        },
        runs: [
          {
            uuid: 'run-1',
            flow: { uuid: FLOW_UUID, name: 'Test Flow' },
            status: 'waiting',
            path: [
              {
                uuid: 'step-1',
                node_uuid: 'node-1',
                arrived_on: new Date().toISOString(),
                exit_uuid: null
              }
            ]
          }
        ],
        environment: {
          date_format: 'YYYY-MM-DD',
          time_format: 'HH:mm',
          timezone: 'America/New_York',
          allowed_languages: ['eng'],
          default_country: 'US'
        }
      },
      events: [
        {
          type: 'webhook_called',
          created_on: new Date().toISOString(),
          http_logs: [
            {
              elapsed: '123ms',
              request: { attempt: 1, payload: { channel: 'sms' } },
              response: { ok: true }
            },
            {
              duration: '1.2s',
              request: { attempt: 2, payload: { channel: 'whatsapp' } },
              response: { ok: true }
            },
            {
              duration_seconds: '00:01:30',
              request: { attempt: 3, payload: { channel: 'ivr' } },
              response: { ok: true }
            },
            {
              response_time_ms: 2500,
              request: { attempt: 4, payload: { channel: 'email' } },
              response: { ok: true }
            }
          ]
        }
      ],
      contact: {
        uuid: 'fb3787ab-2eda-48a0-a2bc-e2ddadec1286',
        urns: ['tel:+12065551212'],
        fields: {},
        groups: [],
        language: 'eng',
        status: 'active',
        created_on: new Date().toISOString()
      },
      context: {
        contact: {
          uuid: 'fb3787ab-2eda-48a0-a2bc-e2ddadec1286',
          name: 'Alice'
        }
      }
    };

    mockPOST(/\/flow\/simulate\/.*\//, responseWithWebhookEvent);

    const simulator: Simulator = await createSimulator();
    await simulator.updateComplete;
    await openSimulator(simulator);

    const chat = simulator.shadowRoot.querySelector('temba-chat') as any;
    expect(chat).to.exist;
    await chat.updateComplete;

    // the webhook event starts collapsed behind a summary pill —
    // expand it to get at the details button
    await waitForCondition(
      () =>
        !!chat.shadowRoot?.querySelector('temba-label[title="Show details"]'),
      40,
      50
    );
    (
      chat.shadowRoot.querySelector(
        'temba-label[title="Show details"]'
      ) as HTMLElement
    ).click();
    await chat.updateComplete;

    await waitForCondition(
      () => !!chat.shadowRoot?.querySelector('[data-webhook-details]'),
      40,
      50
    );

    const webhookDetailsButton = chat.shadowRoot.querySelector(
      '[data-webhook-details]'
    ) as HTMLElement;
    expect(webhookDetailsButton).to.exist;
    webhookDetailsButton.click();

    await simulator.updateComplete;
    await waitForCondition(
      () =>
        !!simulator.shadowRoot.querySelector('temba-dialog') &&
        (simulator.shadowRoot.querySelector('temba-dialog') as any).open,
      40,
      50
    );

    const dialog = simulator.shadowRoot.querySelector('temba-dialog') as any;
    expect(dialog).to.exist;
    expect(dialog.open).to.be.true;

    const detailsText = dialog.textContent || '';
    expect(detailsText).to.match(/4\s+attempts/);
    expect(detailsText).to.contain('1m 34s total elapsed');
    expect(detailsText).to.contain('Attempt 1');
    expect(detailsText).to.contain('Attempt 4');
  });

  it('displays different simulator sizes', async () => {
    mockSimulatorStart();

    const simulator: Simulator = await createSimulator();
    await openSimulator(simulator);

    // get size button - find it by checking if textContent is a size indicator
    let optionButtons = Array.from(
      simulator.shadowRoot.querySelectorAll('.option-btn')
    );
    let sizeButton = optionButtons.find((btn) => {
      const text = btn.textContent?.trim();
      return text === 'S' || text === 'M' || text === 'L';
    }) as HTMLElement;
    expect(sizeButton).to.exist;

    // cycle to next size
    sizeButton.click();
    await simulator.updateComplete;
    await delay(200);

    // verify size changed
    expect(simulator.size).to.equal('large');

    // re-query the button after it updated
    optionButtons = Array.from(
      simulator.shadowRoot.querySelectorAll('.option-btn')
    );
    sizeButton = optionButtons.find((btn) => {
      const text = btn.textContent?.trim();
      return text === 'S' || text === 'M' || text === 'L';
    }) as HTMLElement;

    // cycle to next size
    sizeButton.click();
    await simulator.updateComplete;
    await delay(200);

    expect(simulator.size).to.equal('small');
  });

  it('verifies simulator endpoint configuration', async () => {
    const simulator: Simulator = await createSimulator();

    // verify endpoint is set correctly from flow prop
    expect(simulator.endpoint).to.equal(`/flow/simulate/${FLOW_UUID}/`);

    // change flow prop and verify endpoint updates
    simulator.flow = 'different-flow-456';
    await simulator.updateComplete;

    expect(simulator.endpoint).to.equal('/flow/simulate/different-flow-456/');
  });

  // --- Cookie persistence ---

  describe('cookie persistence', () => {
    afterEach(() => {
      setCookie('simulator', '{}');
    });

    it('restores settings from simulator cookie', async () => {
      const simulator = await createSimulatorRaw(
        {},
        JSON.stringify({
          size: 'large',
          following: false,
          contextExplorerOpen: true
        })
      );
      expect(simulator.size).to.equal('large');
      expect((simulator as any).following).to.equal(false);
      expect((simulator as any).contextExplorerOpen).to.equal(true);
    });

    it('ignores invalid size values from cookie', async () => {
      const simulator = await createSimulatorRaw(
        {},
        JSON.stringify({
          size: 'gigantic',
          following: true,
          contextExplorerOpen: false
        })
      );
      // should keep default since 'gigantic' is not a valid size
      expect(simulator.size).to.equal('small');
    });

    it('ignores non-boolean following/contextExplorerOpen values from cookie', async () => {
      const simulator = await createSimulatorRaw(
        {},
        JSON.stringify({
          size: 'medium',
          following: 'yes',
          contextExplorerOpen: 42
        })
      );
      expect(simulator.size).to.equal('medium');
      // should keep defaults since values aren't booleans
      expect((simulator as any).following).to.equal(true);
      expect((simulator as any).contextExplorerOpen).to.equal(false);
    });

    it('saves settings to cookie when properties change', async () => {
      const simulator = await createSimulatorRaw({}, '{}');
      simulator.size = 'large';
      await simulator.updateComplete;

      const settings = JSON.parse(getCookie('simulator') || '{}');
      expect(settings.size).to.equal('large');
    });

    it('handles malformed cookie gracefully', async () => {
      const simulator = await createSimulatorRaw({}, 'not-valid-json{');
      // should use defaults without throwing
      expect(simulator.size).to.equal('small');
      expect((simulator as any).following).to.equal(true);
    });
  });
});

import { produce } from 'immer';
import { FlowDefinition } from '../store/flow-definition';
import { normalizeUuid } from '../store/identity';

export interface FlowDependency {
  type: string;
  name: string;
  uuid?: string;
  key?: string;
  missing?: boolean;
}

const dependencyIdentity = (dependency: FlowDependency): string | null => {
  const identity = dependency.uuid || dependency.key;
  return identity ? `${dependency.type}:${identity}` : null;
};

/**
 * Returns a definition whose embedded reference names have been replaced by
 * the canonical dependency names supplied by the server. References with a
 * UUID are safe to recognize anywhere in the definition because flow-owned
 * UUIDs don't appear in its dependency list. Field references use keys and
 * only occur under a `field` property; scoping keyed matching there avoids
 * confusing a field key with a result name or another keyed structure.
 */
export const resolveDependencyNames = (
  definition: FlowDefinition,
  dependencies: FlowDependency[] = []
): FlowDefinition => {
  if (!definition || dependencies.length === 0) {
    return definition;
  }

  const namesByUuid = new Map<string, string>();
  const fieldNamesByKey = new Map<string, string>();
  for (const dependency of dependencies) {
    if (dependency.uuid && dependency.name != null) {
      // normalized on both set and lookup so a reference embedded in the
      // definition in a non-canonical form still matches, the same way the
      // store's asset cache resolves it
      namesByUuid.set(normalizeUuid(dependency.uuid), dependency.name);
    } else if (
      dependency.type === 'field' &&
      dependency.key &&
      dependency.name != null
    ) {
      fieldNamesByKey.set(dependency.key, dependency.name);
    }
  }

  return produce(definition, (draft: any) => {
    const visit = (value: any, propertyName?: string) => {
      if (!value || typeof value !== 'object') {
        return;
      }
      if (Array.isArray(value)) {
        // keep the owning property name so `field` scoping still applies to
        // references nested in an array
        value.forEach((item) => visit(item, propertyName));
        return;
      }

      if (typeof value.uuid === 'string' && 'name' in value) {
        const canonical = namesByUuid.get(normalizeUuid(value.uuid));
        if (canonical != null) {
          value.name = canonical;
        }
      } else if (
        propertyName === 'field' &&
        typeof value.key === 'string' &&
        'name' in value
      ) {
        const canonical = fieldNamesByKey.get(value.key);
        if (canonical != null) {
          value.name = canonical;
        }
      }

      for (const [key, child] of Object.entries(value)) {
        visit(child, key);
      }
    };

    visit(draft);
  });
};

/**
 * Replaces every matching dependency whose canonical name has changed. Assets
 * the loaded flow isn't interested in are ignored.
 */
export const replaceDependencies = (
  dependencies: FlowDependency[] = [],
  changed: FlowDependency[]
): FlowDependency[] | null => {
  const changedByIdentity = new Map<string, FlowDependency>();
  for (const dependency of changed) {
    const identity = dependencyIdentity(dependency);
    if (identity) {
      changedByIdentity.set(identity, dependency);
    }
  }

  let replaced = false;
  const updated = dependencies.map((dependency) => {
    const identity = dependencyIdentity(dependency);
    const replacement = identity ? changedByIdentity.get(identity) : null;
    if (!replacement || replacement.name === dependency.name) {
      return dependency;
    }
    replaced = true;
    return { ...dependency, name: replacement.name };
  });
  return replaced ? updated : null;
};

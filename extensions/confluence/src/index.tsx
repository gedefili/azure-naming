/*
 * Repository: azure-naming
 * Path: extensions/confluence/src/index.tsx
 * Purpose: Forge UI Kit macro and resolver entrypoints for the Naming claim macro
 * Author: GitHub Copilot
 * Created: 2026-04-26
 * Last-Modified: 2026-04-27
 * Version: 0.2.0
 */
import React, {
  // ForgeUI is the namespace import retained for the JSX runtime hint.
  default as ForgeUI,
  render,
  Macro,
  MacroConfig,
  Fragment,
  Text,
  Strong,
  Heading,
  TextField,
  Select,
  Option,
  useConfig,
  useState,
  Button,
  ButtonSet,
} from "@forge/ui";
import Resolver from "@forge/resolver";
import { callNamingApi } from "./api";
import { sanitizeErrorBody } from "./http";
import { createClaim, listClaims, releaseClaim } from "./resolvers";

interface MacroConfigShape {
  resourceType?: string;
  region?: string;
  environment?: string;
  project?: string;
}

interface ClaimSummary {
  name: string;
  resource_type?: string;
  region?: string;
  environment?: string;
}

const Config = (): unknown => (
  <MacroConfig>
    <TextField name="resourceType" label="Resource type" />
    <Select name="region" label="Region">
      <Option label="wus2" value="wus2" defaultSelected />
      <Option label="eus1" value="eus1" />
      <Option label="eus2" value="eus2" />
    </Select>
    <Select name="environment" label="Environment">
      <Option label="dev" value="dev" defaultSelected />
      <Option label="alt" value="alt" />
      <Option label="stg" value="stg" />
      <Option label="prd" value="prd" />
    </Select>
    <TextField name="project" label="Project (optional)" />
  </MacroConfig>
);

const App = (): unknown => {
  const config = (useConfig() as MacroConfigShape) ?? {};
  const [claim, setClaim] = useState<ClaimSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  const onClaim = async (): Promise<void> => {
    if (!config.resourceType || !config.region || !config.environment) {
      setError("Please configure resource type, region, and environment.");
      return;
    }
    try {
      setError(null);
      const result = await callNamingApi<ClaimSummary>("/claim", {
        method: "POST",
        body: {
          resource_type: config.resourceType,
          region: config.region,
          environment: config.environment,
          project: config.project,
          source: "confluence-forge",
        },
      });
      setClaim(result);
    } catch (e) {
      setError(sanitizeErrorBody(e instanceof Error ? e.message : String(e)));
    }
  };

  return (
    <Fragment>
      <Heading size="medium">Azure Name</Heading>
      {claim ? (
        <Fragment>
          <Text>
            <Strong>{claim.name}</Strong>
          </Text>
          <Text>
            {claim.resource_type ?? config.resourceType} · {claim.region ?? config.region} ·{" "}
            {claim.environment ?? config.environment}
          </Text>
        </Fragment>
      ) : (
        <Fragment>
          <Text>
            No name claimed yet for {config.resourceType ?? "?"} in{" "}
            {config.region ?? "?"} / {config.environment ?? "?"}.
          </Text>
          <ButtonSet>
            <Button text="Claim Name" onClick={onClaim} />
          </ButtonSet>
          {error ? <Text>Error: {error}</Text> : null}
        </Fragment>
      )}
    </Fragment>
  );
};

export const macroHandler = render(<Macro app={<App />} />);
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export const configHandler = render(<Config />);

const resolver = new Resolver();
const api = { call: callNamingApi };

resolver.define("listClaims", async ({ payload }) =>
  listClaims(api, (payload ?? null) as Parameters<typeof listClaims>[1]),
);

resolver.define("claim", async ({ payload }) =>
  createClaim(api, payload as Parameters<typeof createClaim>[1]),
);

resolver.define("release", async ({ payload }) =>
  releaseClaim(api, payload as Parameters<typeof releaseClaim>[1]),
);

export const resolverHandler = resolver.getDefinitions();

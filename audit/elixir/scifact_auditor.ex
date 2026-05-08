defmodule SrBench.ScifactAuditor do
  @moduledoc """
  Audits SciFact gold labels by asking an LLM to evaluate whether the
  gold annotation (SUPPORT/CONTRADICT) is correct given the claim and evidence.

  Each claim gets a single audit pass that returns AGREE/DISAGREE/DEBATABLE
  with detailed reasoning about why the gold label may or may not be correct.
  """

  require Logger

  @model "gpt-5.4-mini"
  @temperature 0.3
  @max_tokens 600

  @audit_schema %{
    type: "json_schema",
    json_schema: %{
      name: "label_audit",
      strict: true,
      schema: %{
        type: "object",
        properties: %{
          gold_assessment: %{
            type: "string",
            description: "One of: agree, disagree, debatable"
          },
          reasoning: %{
            type: "string",
            description: "Detailed explanation of whether the gold label is correct (3-5 sentences)"
          },
          error_type: %{
            type: "string",
            description: "If disagree/debatable: one of: claim_imprecise, causal_overclaim, generalization_beyond_evidence, numerical_mismatch, negation_missed, direction_reversed, annotation_convention, other, none"
          },
          correct_label: %{
            type: "string",
            description: "What the label should be: support, contradict, or ambiguous"
          }
        },
        required: ["gold_assessment", "reasoning", "error_type", "correct_label"],
        additionalProperties: false
      }
    }
  }

  @audit_prompt """
  You are a scientific peer reviewer auditing a benchmark dataset for annotation quality. \
  Your task is to evaluate whether the gold label assigned to a scientific claim is CORRECT \
  given the provided evidence.

  The dataset labels claims as either SUPPORT (the evidence supports the claim) or \
  CONTRADICT (the evidence contradicts the claim).

  Evaluate rigorously:
  - Does the evidence actually support/contradict the claim as stated?
  - Is the claim precisely worded, or does imprecise wording make the label debatable?
  - Are there causal overclaims, generalizations beyond the evidence, or numerical mismatches?
  - Would a domain expert agree with this gold label?

  Be honest: if the gold label is clearly correct, say AGREE. Only flag issues you are \
  confident about. But do not hesitate to flag genuine annotation errors.

  Return your assessment as JSON.
  """

  def audit_all(opts \\ []) do
    api_key = Keyword.get_lazy(opts, :api_key, fn ->
      Application.get_env(:colony_runtime, :llm_api_key) ||
        System.get_env("OPENAI_API_KEY")
    end)

    base_url = Keyword.get(opts, :base_url, "https://api.openai.com")
    concurrency = Keyword.get(opts, :concurrency, 15)

    {:ok, claims} = SrBench.ScifactLoader.load(:dev)
    Logger.info("Auditing #{length(claims)} SciFact dev claims")

    total_usage = :counters.new(2, [:atomics])
    processed = :counters.new(1, [:atomics])
    total = length(claims)

    results =
      claims
      |> Task.async_stream(
        fn claim ->
          gold_label = if claim.label == "true", do: "SUPPORT", else: "CONTRADICT"

          user_prompt = """
          Scientific claim: "#{claim.claim}"

          Gold label: #{gold_label}

          Evidence (from the cited paper):
          #{claim.main_text}
          """

          body = %{
            model: @model,
            messages: [
              %{role: "system", content: @audit_prompt},
              %{role: "user", content: user_prompt}
            ],
            temperature: @temperature,
            max_completion_tokens: @max_tokens,
            response_format: @audit_schema
          }

          case do_api_call(base_url, api_key, body) do
            {:ok, result, usage} ->
              :counters.add(total_usage, 1, usage.input_tokens)
              :counters.add(total_usage, 2, usage.output_tokens)
              :counters.add(processed, 1, 1)
              done = :counters.get(processed, 1)
              if rem(done, 50) == 0, do: Logger.info("Audit progress: #{done}/#{total}")

              %{
                id: claim.id,
                claim: claim.claim,
                gold_label: gold_label,
                doc_id: claim.doc_id,
                assessment: result["gold_assessment"],
                reasoning: result["reasoning"],
                error_type: result["error_type"],
                correct_label: result["correct_label"]
              }

            {:error, reason} ->
              :counters.add(processed, 1, 1)
              Logger.warning("Audit failed for claim #{claim.id}: #{inspect(reason)}")

              %{
                id: claim.id,
                claim: claim.claim,
                gold_label: gold_label,
                doc_id: claim.doc_id,
                assessment: "error",
                reasoning: inspect(reason),
                error_type: "none",
                correct_label: "unknown"
              }
          end
        end,
        max_concurrency: concurrency,
        timeout: 120_000,
        on_timeout: :kill_task
      )
      |> Enum.map(fn
        {:ok, r} -> r
        {:exit, _} -> nil
      end)
      |> Enum.reject(&is_nil/1)

    usage = %{
      input_tokens: :counters.get(total_usage, 1),
      output_tokens: :counters.get(total_usage, 2)
    }

    # Summary
    by_assessment = Enum.frequencies_by(results, & &1.assessment)
    by_error_type = results
      |> Enum.reject(& &1.assessment == "agree")
      |> Enum.frequencies_by(& &1.error_type)

    summary = %{
      total: length(results),
      by_assessment: by_assessment,
      by_error_type: by_error_type
    }

    Logger.info("Audit complete: #{inspect(by_assessment)}")
    Logger.info("Error types: #{inspect(by_error_type)}")

    # Save
    output = %{
      dataset: "scifact",
      split: "dev",
      model: @model,
      timestamp: DateTime.utc_now() |> DateTime.to_iso8601(),
      summary: summary,
      usage: Map.merge(usage, %{
        cost_usd: usage.input_tokens * 0.25 / 1_000_000 + usage.output_tokens * 1.0 / 1_000_000
      }),
      results: results
    }

    results_dir = Application.app_dir(:sr_bench, "priv/scifact_results")
    File.mkdir_p!(results_dir)
    ts = DateTime.utc_now() |> DateTime.to_iso8601() |> String.replace(":", "-")
    path = Path.join(results_dir, "scifact_audit_#{@model}_n#{length(results)}_#{ts}.json")
    File.write!(path, Jason.encode!(output, pretty: true))
    Logger.info("Saved audit to #{path}")

    {:ok, output}
  end

  defp do_api_call(base_url, api_key, body, attempt \\ 0) do
    if attempt > 3 do
      {:error, :max_retries_exceeded}
    else
      result = Req.request(
        url: "#{base_url}/v1/chat/completions",
        method: :post,
        headers: [
          {"content-type", "application/json"},
          {"authorization", "Bearer #{api_key}"}
        ],
        json: body,
        receive_timeout: 60_000
      )

      case result do
        {:ok, %{status: 200, body: resp}} ->
          parse_response(resp)

        {:ok, %{status: 429}} ->
          delay = 1_000 * Integer.pow(2, attempt)
          Process.sleep(delay)
          do_api_call(base_url, api_key, body, attempt + 1)

        {:ok, %{status: status, body: resp}} ->
          {:error, {:api_error, status, resp}}

        {:error, reason} ->
          {:error, reason}
      end
    end
  end

  defp parse_response(resp) do
    choice = hd(resp["choices"])
    content = choice["message"]["content"]
    usage = resp["usage"]

    case Jason.decode(content) do
      {:ok, parsed} ->
        {:ok, parsed, %{
          input_tokens: usage["prompt_tokens"] || 0,
          output_tokens: usage["completion_tokens"] || 0
        }}

      {:error, reason} ->
        {:error, {:json_parse_error, reason, content}}
    end
  end
end

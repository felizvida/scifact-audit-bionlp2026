defmodule SrBench.ScifactPilot do
  @moduledoc """
  Pilot runner for SciFact scientific claim verification benchmark.

  Oracle setting: gold evidence abstracts provided.
  Binary: SUPPORT (true) vs CONTRADICT (false).
  Reuses ClaimVerifier with binary mode.
  """

  require Logger

  alias SrBench.ScifactLoader
  alias SrBench.ClaimVerifier

  @pricing %{
    "gpt-5.4-nano" => {0.10, 0.40},
    "gpt-5.4-mini" => {0.25, 1.00}
  }

  def run(opts \\ []) do
    split = Keyword.get(opts, :split, :dev)
    seed = Keyword.get(opts, :seed, 42)
    strategy = Keyword.get(opts, :strategy, :ensemble)
    model = Keyword.get(opts, :model, "gpt-5.4-nano")
    concurrency = Keyword.get(opts, :concurrency, 30)

    Logger.info("=== SciFact Pilot: #{strategy}, #{model}, split=#{split} ===")

    {:ok, claims} = ScifactLoader.load(split, shuffle: true, seed: seed)

    limit = Keyword.get(opts, :limit)
    claims = if limit, do: Enum.take(claims, limit), else: claims

    actual_n = length(claims)
    Logger.info("Loaded #{actual_n} claims with gold evidence")
    Logger.info("Label distribution: #{inspect(Enum.frequencies_by(claims, & &1.label))}")

    start_time = System.monotonic_time(:millisecond)

    {:ok, results, usage} = ClaimVerifier.verify_batch(claims,
      strategy: strategy,
      model: model,
      binary: true,
      concurrency: concurrency
    )

    elapsed_ms = System.monotonic_time(:millisecond) - start_time

    metrics = ClaimVerifier.evaluate(results)

    {price_in, price_out} = Map.get(@pricing, model, {0.25, 1.00})
    cost_in = usage.input_tokens * price_in / 1_000_000
    cost_out = usage.output_tokens * price_out / 1_000_000
    total_cost = cost_in + cost_out

    Logger.info("")
    Logger.info("=== SciFact Results ===")
    Logger.info("Accuracy: #{Float.round(metrics.accuracy * 100, 1)}% (#{metrics.correct}/#{metrics.total})")
    Logger.info("Macro F1: #{Float.round(metrics.macro_f1 * 100, 1)}%")

    per_true = metrics.per_class["true"]
    per_false = metrics.per_class["false"]
    Logger.info("SUPPORT  — P=#{pct(per_true.precision)} R=#{pct(per_true.recall)} F1=#{pct(per_true.f1)} (n=#{per_true.support})")
    Logger.info("CONTRADICT — P=#{pct(per_false.precision)} R=#{pct(per_false.recall)} F1=#{pct(per_false.f1)} (n=#{per_false.support})")

    Logger.info("")
    Logger.info("=== Cost ===")
    Logger.info("Time: #{Float.round(elapsed_ms / 1000, 1)}s")
    Logger.info("Tokens: #{usage.input_tokens} in / #{usage.output_tokens} out")
    Logger.info("Cost: $#{Float.round(total_cost, 4)}")
    Logger.info("Cost/claim: $#{Float.round(total_cost / max(actual_n, 1), 6)}")

    save_results(results, metrics, usage, total_cost, elapsed_ms, opts, actual_n)

    {:ok, %{metrics: metrics, results: results, usage: usage, cost: total_cost}}
  end

  defp pct(v), do: "#{Float.round(v * 100, 1)}%"

  defp save_results(results, metrics, usage, cost, elapsed_ms, opts, n) do
    dir = Application.app_dir(:sr_bench, "priv/scifact_results")
    File.mkdir_p!(dir)

    timestamp = DateTime.utc_now() |> DateTime.to_iso8601() |> String.replace(~r/[:\.]/, "-")
    strategy = Keyword.get(opts, :strategy, :ensemble)
    model = Keyword.get(opts, :model, "gpt-5.4-nano") |> String.replace("/", "_")

    filename = "scifact_#{strategy}_#{model}_n#{n}_#{timestamp}.json"
    path = Path.join(dir, filename)

    serialized =
      Enum.map(results, fn {claim, result} ->
        %{
          id: claim.id,
          claim: claim.claim,
          doc_id: claim.doc_id,
          gold_label: claim.label,
          predicted: result["verdict"],
          confidence: result["confidence"],
          reasoning: result["reasoning"],
          votes: result["votes"]
        }
      end)

    per_true = metrics.per_class["true"]
    per_false = metrics.per_class["false"]

    data = %{
      config: %{
        dataset: "scifact",
        setting: "oracle",
        strategy: strategy,
        model: Keyword.get(opts, :model, "gpt-5.4-nano"),
        split: Keyword.get(opts, :split, :dev),
        seed: Keyword.get(opts, :seed, 42),
        n: n
      },
      metrics: %{
        accuracy: metrics.accuracy,
        macro_f1: metrics.macro_f1,
        correct: metrics.correct,
        total: metrics.total,
        errors: metrics.errors,
        support: %{precision: per_true.precision, recall: per_true.recall, f1: per_true.f1, n: per_true.support},
        contradict: %{precision: per_false.precision, recall: per_false.recall, f1: per_false.f1, n: per_false.support}
      },
      usage: usage,
      cost_usd: cost,
      elapsed_ms: elapsed_ms,
      results: serialized
    }

    File.write!(path, Jason.encode!(data, pretty: true))
    Logger.info("Results saved to #{path}")
  end
end

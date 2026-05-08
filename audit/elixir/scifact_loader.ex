defmodule SrBench.ScifactLoader do
  @moduledoc """
  Downloads and loads the SciFact scientific claim verification dataset.

  Source: allenai/scifact on GitHub.
  ~1,409 expert-written scientific claims against 5,183 PubMed abstracts.
  Labels: SUPPORT / CONTRADICT (binary).
  Oracle setting: gold evidence abstracts provided.
  """

  require Logger

  @tarball_url "https://scifact.s3-us-west-2.amazonaws.com/release/latest/data.tar.gz"

  def dataset_dir do
    Application.app_dir(:sr_bench, "priv/scifact_dataset")
  end

  def download do
    dir = dataset_dir()
    File.mkdir_p!(dir)

    # Check if already extracted
    corpus_path = Path.join(dir, "corpus.jsonl")

    unless File.exists?(corpus_path) do
      tarball_path = Path.join(dir, "data.tar.gz")

      unless File.exists?(tarball_path) do
        Logger.info("Downloading SciFact dataset from S3...")

        case Req.get(@tarball_url, into: File.stream!(tarball_path), receive_timeout: 120_000) do
          {:ok, %{status: 200}} ->
            Logger.info("Downloaded to #{tarball_path}")

          {:ok, %{status: status}} ->
            File.rm(tarball_path)
            raise "HTTP #{status} downloading SciFact tarball"

          {:error, reason} ->
            File.rm(tarball_path)
            raise "Download failed: #{inspect(reason)}"
        end
      end

      # Extract — files are under data/ in the tarball
      Logger.info("Extracting SciFact dataset...")
      {output, 0} = System.cmd("tar", ["xzf", tarball_path, "-C", dir, "--strip-components=1"],
        stderr_to_stdout: true)

      if output != "", do: Logger.info("tar: #{output}")
      Logger.info("Extracted SciFact dataset to #{dir}")
    end

    :ok
  end

  @doc """
  Load the corpus as a map of doc_id => %{title, abstract_text, sentences}.
  """
  def load_corpus do
    path = Path.join(dataset_dir(), "corpus.jsonl")
    unless File.exists?(path), do: download()

    path
    |> File.stream!()
    |> Stream.map(&String.trim/1)
    |> Stream.reject(&(&1 == ""))
    |> Stream.map(&Jason.decode!/1)
    |> Enum.reduce(%{}, fn doc, acc ->
      doc_id = to_string(doc["doc_id"])
      sentences = doc["abstract"] || []
      abstract_text = Enum.join(sentences, " ")

      Map.put(acc, doc_id, %{
        title: doc["title"] || "",
        sentences: sentences,
        abstract_text: abstract_text
      })
    end)
  end

  @doc """
  Load claims with gold evidence for the oracle setting.

  Returns claims with evidence text joined from the corpus.
  Each claim has:
  - :id, :claim, :label ("support" or "contradict"), :evidence_text, :doc_id

  Options:
  - :limit — max claims
  - :shuffle — randomize (default: false)
  - :seed — random seed
  """
  def load(split \\ :dev, opts \\ []) do
    split_file = case split do
      :train -> "claims_train.jsonl"
      :dev -> "claims_dev.jsonl"
      :test -> "claims_test.jsonl"
    end

    path = Path.join(dataset_dir(), split_file)
    unless File.exists?(path), do: download()

    corpus = load_corpus()

    limit = Keyword.get(opts, :limit)
    shuffle = Keyword.get(opts, :shuffle, false)
    seed = Keyword.get(opts, :seed)

    claims =
      path
      |> File.stream!()
      |> Stream.map(&String.trim/1)
      |> Stream.reject(&(&1 == ""))
      |> Stream.map(&Jason.decode!/1)
      |> Enum.flat_map(fn raw -> parse_claim(raw, corpus) end)

    claims =
      if shuffle do
        if seed, do: :rand.seed(:exsss, {seed, seed, seed})
        Enum.shuffle(claims)
      else
        claims
      end

    claims = if limit, do: Enum.take(claims, limit), else: claims

    {:ok, claims}
  end

  defp parse_claim(raw, corpus) do
    evidence = raw["evidence"] || %{}

    if evidence == %{} do
      # No gold evidence (NEI) — skip for oracle evaluation
      []
    else
      # One result per evidence document
      Enum.flat_map(evidence, fn {doc_id_str, rationales} ->
        doc = Map.get(corpus, doc_id_str)

        if doc && rationales != [] do
          label = hd(rationales)["label"]
          normalized = normalize_label(label)

          # Build evidence text from rationale sentences
          rationale_sentences =
            rationales
            |> Enum.flat_map(fn r -> r["sentences"] || [] end)
            |> Enum.uniq()
            |> Enum.sort()

          evidence_text = if rationale_sentences != [] do
            # Use specific rationale sentences
            rationale_sentences
            |> Enum.map(fn idx -> Enum.at(doc.sentences, idx, "") end)
            |> Enum.join(" ")
          else
            doc.abstract_text
          end

          [%{
            id: raw["id"],
            claim: raw["claim"],
            label: normalized,
            # For ClaimVerifier compatibility: evidence goes in main_text
            main_text: "Title: #{doc.title}\n\nAbstract: #{doc.abstract_text}\n\nKey evidence: #{evidence_text}",
            doc_id: doc_id_str,
            subjects: ""
          }]
        else
          []
        end
      end)
    end
  end

  defp normalize_label("SUPPORT"), do: "true"
  defp normalize_label("CONTRADICT"), do: "false"
  defp normalize_label(_), do: nil
end

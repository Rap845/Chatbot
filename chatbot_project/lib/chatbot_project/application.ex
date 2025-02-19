defmodule ChatbotProject.Application do
  # See https://hexdocs.pm/elixir/Application.html
  # for more information on OTP Applications
  @moduledoc false

  use Application

  @impl true
  def start(_type, _args) do
    children = [
      ChatbotProjectWeb.Telemetry,
      ChatbotProject.Repo,
      {DNSCluster, query: Application.get_env(:chatbot_project, :dns_cluster_query) || :ignore},
      {Phoenix.PubSub, name: ChatbotProject.PubSub},
      # Start the Finch HTTP client for sending emails
      {Finch, name: ChatbotProject.Finch},
      # Start a worker by calling: ChatbotProject.Worker.start_link(arg)
      # {ChatbotProject.Worker, arg},
      # Start to serve requests, typically the last entry
      ChatbotProjectWeb.Endpoint
    ]

    # See https://hexdocs.pm/elixir/Supervisor.html
    # for other strategies and supported options
    opts = [strategy: :one_for_one, name: ChatbotProject.Supervisor]
    Supervisor.start_link(children, opts)
  end

  # Tell Phoenix to update the endpoint configuration
  # whenever the application is updated.
  @impl true
  def config_change(changed, _new, removed) do
    ChatbotProjectWeb.Endpoint.config_change(changed, removed)
    :ok
  end
end

defmodule ChatbotProject.Repo do
  use Ecto.Repo,
    otp_app: :chatbot_project,
    adapter: Ecto.Adapters.Postgres
end

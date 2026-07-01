class Bwise < Formula
  include Language::Python::Virtualenv

  desc "Bitwarden Wrapper Injecting Secrets Everywhere — thin client over bw serve"
  homepage "https://github.com/leoruiz/bwise"
  url "https://github.com/leoruiz/bwise/archive/refs/tags/v0.2.1.tar.gz"
  sha256 "1c2e3693be18844f4b0a5d273bc3ba0c5ff05d1ca8426aa90d8e53fb02325c14"
  license "MIT"

  depends_on "pinentry-mac"
  depends_on "python@3.12"
  depends_on "uv" => :build

  resource "cyclopts" do
    url "https://files.pythonhosted.org/packages/65/e7/4b3048094559b86a800e0f0de7faf8e6d8213727cf31553ec58453f25abc/cyclopts-4.19.0.tar.gz"
    sha256 "c7532803ab8560d4de8600769793c3de4b2dc8c3b23ec707b989d84d9bae6ff4"
  end

  resource "loguru" do
    url "https://files.pythonhosted.org/packages/3a/05/a1dae3dffd1116099471c643b8924f5aa6524411dc6c63fdae648c4f1aca/loguru-0.7.3.tar.gz"
    sha256 "19480589e77d47b8d85b2c827ad95d49bf31b0dcde16593892eb51dd18706eb6"
  end

  resource "attrs" do
    url "https://files.pythonhosted.org/packages/9a/8e/82a0fe20a541c03148528be8cac2408564a6c9a0cc7e9171802bc1d26985/attrs-26.1.0.tar.gz"
    sha256 "d03ceb89cb322a8fd706d4fb91940737b6642aa36998fe130a9bc96c985eff32"
  end

  resource "docstring-parser" do
    url "https://files.pythonhosted.org/packages/e0/4d/f332313098c1de1b2d2ff91cf2674415cc7cddab2ca1b01ae29774bd5fdf/docstring_parser-0.18.0.tar.gz"
    sha256 "292510982205c12b1248696f44959db3cdd1740237a968ea1e2e7a900eeb2015"
  end

  resource "markdown-it-py" do
    url "https://files.pythonhosted.org/packages/06/ff/7841249c247aa650a76b9ee4bbaeae59370dc8bfd2f6c01f3630c35eb134/markdown_it_py-4.2.0.tar.gz"
    sha256 "04a21681d6fbb623de53f6f364d352309d4094dd4194040a10fd51833e418d49"
  end

  resource "mdurl" do
    url "https://files.pythonhosted.org/packages/d6/54/cfe61301667036ec958cb99bd3efefba235e65cdeb9c84d24a8293ba1d90/mdurl-0.1.2.tar.gz"
    sha256 "bb413d29f5eea38f31dd4754dd7377d4465116fb207585f97bf925588687c1ba"
  end

  resource "pygments" do
    url "https://files.pythonhosted.org/packages/c3/b2/bc9c9196916376152d655522fdcebac55e66de6603a76a02bca1b6414f6c/pygments-2.20.0.tar.gz"
    sha256 "6757cd03768053ff99f3039c1a36d6c0aa0b263438fcab17520b30a303a82b5f"
  end

  resource "rich" do
    url "https://files.pythonhosted.org/packages/c0/8f/0722ca900cc807c13a6a0c696dacf35430f72e0ec571c4275d2371fca3e9/rich-15.0.0.tar.gz"
    sha256 "edd07a4824c6b40189fb7ac9bc4c52536e9780fbbfbddf6f1e2502c31b068c36"
  end

  resource "rich-rst" do
    url "https://files.pythonhosted.org/packages/0b/40/905f612e7bf105d7efefa923542e0c85b731cf29bcc1864331427dbc52b8/rich_rst-2.0.2.tar.gz"
    sha256 "664a669801695c5a126151338f309ce3ea3e0ea081c89a4130b8a4f659911ed9"
  end

  def install
    venv = virtualenv_create(libexec, "python3.12")
    venv.pip_install resources
    # bwise builds with the uv_build backend, which pip can't compile in
    # isolation; build the (pure-Python) wheel with uv and install it with uv
    # too (Homebrew's pip helper forces --no-binary, which rejects wheels).
    system "uv", "build", "--wheel", "--out-dir", buildpath/"dist"
    system "uv", "pip", "install", "--python", libexec/"bin/python",
           "--no-deps", "--offline",
           Dir[buildpath/"dist/bwise-#{version}-py3-none-any.whl"].first
    bin.install_symlink libexec/"bin/bwise"
  end

  test do
    assert_match "bwise", shell_output("#{bin}/bwise --help")
  end
end

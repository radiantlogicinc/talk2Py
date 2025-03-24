# talk2Py
An SDK to make python apps conversational and agentic

<p align="center">
  <img src="assets/logo.png" alt="talk2Py Logo" width="200"/>
</p>

<p align="center">
  <a href="https://pypi.org/project/talk2py/"><img alt="PyPI" src="https://img.shields.io/pypi/v/talk2py"></a>
  <a href="https://github.com/username/talk2Py/blob/main/LICENSE"><img alt="License" src="https://img.shields.io/github/license/username/talk2py"></a>
  <a href="https://github.com/username/talk2Py/actions"><img alt="Build Status" src="https://img.shields.io/github/workflow/status/username/talk2py/tests"></a>
  <a href="https://github.com/username/talk2Py/stargazers"><img alt="GitHub Stars" src="https://img.shields.io/github/stars/username/talk2py"></a>
</p>

## 📋 Overview

talk2Py is a powerful SDK that enables developers to build conversational and agentic capabilities into their Python applications. With talk2Py, you can easily transform traditional Python applications into interactive agents that can understand natural language, perform actions, and maintain context.

## ✨ Features

- **Natural Language Understanding**: Process and understand user input in natural language
- **Conversation Management**: Maintain context throughout multi-turn conversations
- **Action Execution**: Execute Python functions based on user intents
- **State Tracking**: Keep track of conversation state and user preferences
- **Extensible Architecture**: Easily extend with custom components and integrations

## 🚀 Installation

```bash
pip install talk2py
```

## 🏁 Quick Start

- Create a file called `main.py` and add the following code:

```python
from talk2py import command

# Register functions that can be called by the agent
@command
def get_weather(location: str) -> str:
    """Get the current weather for a location."""
    # Your weather API code here
    return f"It's sunny in {location}!"

```

- Run the command `talk2py.run main.py` and start talking to the agent

- Check out the samples folder for more examples


## 📚 API Reference

For detailed API documentation, visit our [API Reference](https://talk2py.readthedocs.io/).

## 🛠️ Development

### Prerequisites

- Python 3.11+
- uv (optional, for dependency management)

### Setup for Development

```bash
# Clone the repository
git clone https://github.com/username/talk2Py.git
cd talk2Py

# Create a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install development dependencies
pip install -e ".[dev]"
```

### Running Tests

```bash
pytest
```

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

Please check out our [Contributing Guidelines](CONTRIBUTING.md) for more details.

## 📄 License

This project is licensed under the Apache 2.0 License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgements

- Thanks to all contributors who have helped shape talk2Py
- Special thanks to [list relevant libraries/frameworks/people]

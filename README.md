# grain-project

## Table of Contents
- [About the Project](#about-the-project)
- [The Challenge: “Smart Delivery Allocator”](#the-challenge-smart-delivery-allocator)
- [Context](#context)
- [Built With](#built-with)
- [Getting Started](#getting-started)
  - [Installation](#installation)
- [Usage](#usage)
- [Roadmap](#roadmap)
- [License](#license)
- [Contact](#contact)
- [Acknowledgement](#acknowledgement)

---

## About the Project

This project is a proof-of-concept AI-powered delivery allocation system designed to intelligently assign catering orders to delivery specialists, optimizing based on constraints, priorities, and logistics.

---

## The Challenge: “Smart Delivery Allocator”

Build a working prototype of an AI-powered delivery allocation system that intelligently assigns catering orders to delivery specialists based on constraints, priorities, and logistics.

---

## Context

You’re building an internal tool for a catering company (think Grain) that delivers hundreds of orders daily. The operations team currently spends hours manually assigning orders to drivers, trying to balance:

- **Geographic efficiency:** clustering orders by region
- **Time windows:** pickup, setup, teardown constraints
- **Driver preferences and capacity:** regional familiarity, max orders per day
- **Order priorities:** VIP clients, special requirements like pre-setup or weddings

Your task is to create a proof-of-concept that demonstrates how AI can make smart initial allocations, saving hours of manual work and improving logistics efficiency.

---

## Built With

- [Streamlit](https://streamlit.io/)
- Python

---

## Getting Started

### Installation

```bash
uv init
uv sync
uv pip install -r requirements.txt
```

Create a new folder named ./data/.
Add drivers.json and orders.json files under this new folder.


Running the backend

```
python allocator_repeat.py
```

## Usage

## Developer's Guide

## Roadmap

## License

## Contact

## Acknowledgement


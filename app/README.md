# Address Geocoding App

This project is a simple web application built using Streamlit that allows users to convert a list of addresses into their corresponding latitude and longitude using the Geoapify API.

## Features

- Input a list of addresses.
- Convert addresses to geographic coordinates (latitude and longitude).
- Display the results in a user-friendly format.

## Requirements

To run this application, you need to have Python installed on your machine. The required packages are listed in the `requirements.txt` file.

## Setup Instructions

1. Clone the repository:

   ```
   git clone <repository-url>
   cd address-geocoding-app
   ```

2. Create a virtual environment (optional but recommended):

   ```
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```

3. Install the required packages:

   ```
   pip install -r requirements.txt
   ```

4. Create a `.env` file in the root directory and add your Geoapify API key:

   ```
   GEOAPIFY_API_KEY=your_api_key_here
   ```

5. Run the Streamlit application:

   ```
   streamlit run app.py
   ```

## Usage

- Open your web browser and navigate to the URL provided by Streamlit (usually `http://localhost:8501`).
- Enter the addresses you want to geocode in the input field.
- Click the button to convert the addresses to latitude and longitude.
- View the results displayed on the page.

## License

This project is licensed under the MIT License. See the LICENSE file for more details.
FROM python:3.9

WORKDIR /code

# Copy requirements file
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir --upgrade -r requirements.txt

# Copy the app directory
COPY ./app /code/app

# Copy the .env file if it exists
COPY .env* .

# Expose the port the app runs on
EXPOSE 80

# Command to run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "80"]
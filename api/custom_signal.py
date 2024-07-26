from django.dispatch import Signal, receiver
from django.db.models.signals import post_save


# Define custom signal
# job_created = Signal(providing_args=["instance"]) --> This didn't work, I got the solution from here: 
#   https://stackoverflow.com/questions/70466886/typeerror-init-got-an-unexpected-keyword-argument-providing-args
job_created = Signal()
assist_created = Signal()


# brief

The goal is to build a game for diagnostic through elimination 

## starting point ; 
- situation of a patient 

## the process: 
- series of hypothesis
- the guidlines to follow in order to eliminate the hypothesis that aren't correct 

## final state: 
- one hypothesis left. 

## Human process 
a doctor, starts by. getting to know the patient and asking him, series of questions thaht will help reduce the scape of hypothesis , then after the doctor will, start his guidline and start ordering the tests to eliminate the less probable ones. until reaching one last diagnosis .


## Agent 
what we need to reproduce the same real life scenario, and to be able to judge and grade the agent. 

1- we need the data of the cases, the medical guidlines for those cases 

we need dissease from the same family that are hard to diagnose based on simple question/mri/etc ... 

2- we need the guidlines for each one of those disease and how they are diagnosed 

3- we need human body that we can use to apply actions on it ? ((optional))

4- we  need data that link the price of each test that can be ordered by a doctor 
 

5- when seeding a task we chose the diseases that are close to each others and then setup the conditions of the intial patient, and then track the prices and what the hypothesis used by the model and chekck wheter the model has came up with the right diagnosis or not and how much it spent. 

5- building this as game maybe very easy to do. CU , design a consutlation room whith. set of stations where the doctor can take the patient to and order a lab and check what the agent doing 

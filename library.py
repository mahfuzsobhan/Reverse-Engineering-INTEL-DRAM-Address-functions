import subprocess
import re
import os
import logging
from typing import Dict, Tuple, Callable, List

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class DRAMAddressMappingTool:
    def __init__(self, drama_path: str):
        """
        Initialize the tool with the path to the DRAMA tool.
        :param drama_path: Path to the DRAMA tool directory containing the makefile.
        """
        self.drama_path = drama_path
        self.dependencies = ["make", "gcc"]  # Example dependencies to check

    def check_dependencies(self) -> None:
        """
        Checks for required dependencies.
        Raises an exception if any dependency is missing.
        """
        for dep in self.dependencies:
            if subprocess.call(["which", dep], stdout=subprocess.PIPE, stderr=subprocess.PIPE) != 0:
                logging.error(f"Dependency '{dep}' is not installed.")
                raise EnvironmentError(f"Required dependency '{dep}' is missing.")

    def run_make(self, target: str = "all") -> None:
        """
        Runs the makefile with a specified target to compile the DRAMA tool.
        :param target: The make target to execute (default is 'all').
        """
        logging.info(f"Building target '{target}' with make.")
        try:
            subprocess.run(["make", target], cwd=self.drama_path, check=True)
            logging.info(f"Successfully built target: {target}")
        except subprocess.CalledProcessError as e:
            logging.error(f"Failed to build target '{target}': {e}")
            raise RuntimeError(f"Make command failed for target '{target}'.")

    def execute_drama_tool(self, params: List[str] = None) -> str:
        """
        Executes the DRAMA tool with optional parameters and captures its output.
        :param params: List of additional parameters to pass to the tool.
        :return: The output of the DRAMA tool as a string.
        """
        params = params if params else []
        command = ["./drama_tool"] + params
        try:
            logging.info(f"Executing DRAMA tool with parameters: {params}")
            result = subprocess.run(command, cwd=self.drama_path, 
                                    check=True, capture_output=True, text=True)
            logging.info("DRAMA tool executed successfully.")
            return result.stdout
        except subprocess.CalledProcessError as e:
            logging.error(f"Error running DRAMA tool: {e}")
            raise RuntimeError("Execution of DRAMA tool failed.")

    def parse_drama_output(self, output: str) -> Dict[str, Tuple[int, int]]:
        """
        Parses the output from the DRAMA tool to extract address mapping details, including bit positions.
        :param output: Raw output string from the DRAMA tool.
        :return: Dictionary containing DRAM address mapping details (start and length of bitfields).
        """
        mapping_info = {}
        
        # Example parsing pattern to find address mappings with bit ranges (adjust regex as needed)
        for line in output.splitlines():
            match = re.match(r"(Row|Column|Bank) bits (\d+)-(\d+)", line)
            if match:
                key = match.group(1).lower()
                start, end = int(match.group(2)), int(match.group(3))
                mapping_info[key] = (start, end - start + 1)  # Store bit position and length
                
        logging.info("Parsed DRAM mapping info: %s", mapping_info)
        return mapping_info

    def generate_address_mapping_function(self, mapping_info: Dict[str, Tuple[int, int]]) -> Callable[[int], Tuple[int, int, int]]:
        """
        Generates a function to map a physical address to DRAM coordinates based on bit positions.
        :param mapping_info: Dictionary with DRAM address mapping details (start and length of bitfields).
        :return: A function that maps physical addresses to (row, column, bank).
        """
        
        def extract_bits(value: int, start: int, length: int) -> int:
            """Helper function to extract bits from 'value' at 'start' position with 'length' bits."""
            mask = (1 << length) - 1
            return (value >> start) & mask
        
        def address_mapping_func(phys_addr: int) -> Tuple[int, int, int]:
            """
            Maps a physical address to DRAM coordinates (row, column, bank) based on extracted bit fields.
            :param phys_addr: Physical address to map.
            :return: Tuple with (row, column, bank).
            """
            row = extract_bits(phys_addr, *mapping_info.get("row", (0, 0)))
            col = extract_bits(phys_addr, *mapping_info.get("column", (0, 0)))
            bank = extract_bits(phys_addr, *mapping_info.get("bank", (0, 0)))
            return row, col, bank

        logging.info("Address mapping function generated based on bit positions.")
        return address_mapping_func

    def run_and_generate_mapping(self) -> Callable[[int], Tuple[int, int, int]]:
        """
        Full pipeline: check dependencies, build the tool, run it, parse the output, and generate the address mapping function.
        :return: The generated address mapping function.
        """
        # Step 1: Check dependencies
        self.check_dependencies()

        # Step 2: Build the tool
        self.run_make()
        
        # Step 3: Execute the DRAMA tool and get its output
        output = self.execute_drama_tool()
        if not output:
            raise RuntimeError("Failed to execute DRAMA tool.")
        
        # Step 4: Parse the output to get mapping information
        mapping_info = self.parse_drama_output(output)
        
        # Step 5: Generate and return the address mapping function
        return self.generate_address_mapping_function(mapping_info)

# Usage example:
if __name__ == "__main__":
    drama_tool_path = "drama"  # Update this path as needed
    dram_tool = DRAMAddressMappingTool(drama_tool_path)
    
    # Run the complete pipeline and get the address mapping function
    try:
        address_mapping_func = dram_tool.run_and_generate_mapping()
        
        # Test the generated function with a sample physical address
        phys_address = 0x12345678
        row, column, bank = address_mapping_func(phys_address)
        print(f"Physical Address: {hex(phys_address)} -> Row: {row}, Column: {column}, Bank: {bank}")
    except (EnvironmentError, RuntimeError) as e:
        logging.error("An error occurred: %s", e)

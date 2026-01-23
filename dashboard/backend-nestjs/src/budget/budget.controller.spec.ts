import { Test, TestingModule } from '@nestjs/testing';
import { NotFoundException } from '@nestjs/common';
import { BudgetController } from './budget.controller';
import { BudgetService } from './budget.service';

describe('BudgetController', () => {
  let controller: BudgetController;
  let budgetService: jest.Mocked<BudgetService>;

  const mockBudgetService = {
    getBudget: jest.fn(),
    getReport: jest.fn(),
  };

  beforeEach(async () => {
    jest.clearAllMocks();

    const module: TestingModule = await Test.createTestingModule({
      controllers: [BudgetController],
      providers: [{ provide: BudgetService, useValue: mockBudgetService }],
    }).compile();

    controller = module.get<BudgetController>(BudgetController);
    budgetService = module.get(BudgetService);
  });

  describe('getBudget', () => {
    it('should return budget status', async () => {
      const budget = { totalSpentUsd: 5.0, enabled: true };
      budgetService.getBudget.mockResolvedValueOnce(budget);

      const result = await controller.getBudget('test');

      expect(result).toEqual(budget);
      expect(budgetService.getBudget).toHaveBeenCalledWith('test');
    });
  });

  describe('getReport', () => {
    it('should return budget report', async () => {
      const report = { status: {}, taskSpending: [] };
      budgetService.getReport.mockResolvedValueOnce(report);

      const result = await controller.getReport('test');

      expect(result).toEqual(report);
      expect(budgetService.getReport).toHaveBeenCalledWith('test');
    });
  });
});
